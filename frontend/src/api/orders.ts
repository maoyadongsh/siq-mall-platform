import type { OrderDetail, OrderSummary, Page } from '@/types/models'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

interface PendingCommand {
  key: string
  path: string
  data: Record<string, unknown>
}

interface OperationReceipt {
  resource_type: string
  resource_id: string
}

function storageKey(action: string, target: string): string {
  return ['siq.order.v1', useUserStore().profile?.id, action, target].join(':')
}

export function pendingCommand(action: string, target: string): PendingCommand | null {
  return JSON.parse(sessionStorage.getItem(storageKey(action, target)) || 'null') as PendingCommand | null
}

// A lost response persists the exact operation. Recovery always uses the original key.
export async function submitCommand<T>(
  action: string,
  target: string,
  path: string,
  data: Record<string, unknown>,
): Promise<T> {
  const storage = storageKey(action, target)
  const prior = pendingCommand(action, target)
  const op = prior || { key: crypto.randomUUID(), path, data }
  sessionStorage.setItem(storage, JSON.stringify(op))
  try {
    if (prior && action === 'order.create') {
      try {
        const order = await request.get<T>('/orders/by-intent/' + String(op.data.intent_id) + '/', {
          skipErrorMessage: true,
        })
        sessionStorage.removeItem(storage)
        return order
      } catch (e) {
        const error = e as { response?: { status: number } }
        if (error.response?.status !== 404) throw e
      }
    }
    if (prior && action !== 'order.create') {
      try {
        const receipt = await request.get<OperationReceipt>(
          '/operations/' + action + '/' + op.key + '/',
          { skipErrorMessage: true },
        )
        const prefix =
          receipt.resource_type === 'payment'
            ? '/payments/'
            : action === 'order.ship'
              ? '/ops/orders/'
              : '/orders/'
        const current = await request.get<T>(prefix + receipt.resource_id + '/')
        sessionStorage.removeItem(storage)
        return current
      } catch (e) {
        const error = e as { response?: { status: number } }
        if (error.response?.status !== 404) throw e
      }
    }
    const result = await request.post<T>(op.path, op.data, {
      headers: { 'Idempotency-Key': op.key },
    })
    sessionStorage.removeItem(storage)
    return result
  } catch (e) {
    const error = e as { response?: { status: number; data?: { code?: number } } }
    if (
      [400, 403, 404, 409].includes(error.response?.status ?? 0) &&
      error.response?.data?.code !== 10009
    )
      sessionStorage.removeItem(storage)
    throw e
  }
}

export const getOrder = (no: string, ops = false): Promise<OrderDetail> =>
  request.get((ops ? '/ops' : '') + '/orders/' + no + '/')

export const getOrders = (
  ops: boolean,
  params?: Record<string, string | number | undefined>,
): Promise<Page<OrderSummary>> => request.get((ops ? '/ops' : '') + '/orders/', { params })

export const statusNames: Record<string, string> = {
  pending: '待付款',
  paid: '待发货',
  shipped: '待收货',
  completed: '已完成',
  canceled: '已取消',
}
