import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

function storageKey(action, target) {
  return ['siq.order.v1', useUserStore().profile.id, action, target].join(':')
}
export function pendingCommand(action, target) {
  return JSON.parse(sessionStorage.getItem(storageKey(action, target)) || 'null')
}
// A lost response persists the exact operation. Recovery always uses the original key.
export async function submitCommand(action, target, path, data) {
  const storage = storageKey(action, target)
  const prior = pendingCommand(action, target)
  const op = prior || { key: crypto.randomUUID(), path, data }
  sessionStorage.setItem(storage, JSON.stringify(op))
  try {
    if (prior && action === 'order.create') {
      try {
        const order = await request.get('/orders/by-intent/' + op.data.intent_id + '/', {
          skipErrorMessage: true,
        })
        sessionStorage.removeItem(storage)
        return order
      } catch (e) {
        if (e.response?.status !== 404) throw e
      }
    }
    if (prior && action !== 'order.create') {
      try {
        const receipt = await request.get('/operations/' + action + '/' + op.key + '/', {
          skipErrorMessage: true,
        })
        const prefix =
          receipt.resource_type === 'payment'
            ? '/payments/'
            : action === 'order.ship'
              ? '/ops/orders/'
              : '/orders/'
        const current = await request.get(prefix + receipt.resource_id + '/')
        sessionStorage.removeItem(storage)
        return current
      } catch (e) {
        if (e.response?.status !== 404) throw e
      }
    }
    const result = await request.post(op.path, op.data, { headers: { 'Idempotency-Key': op.key } })
    sessionStorage.removeItem(storage)
    return result
  } catch (e) {
    if ([400, 403, 404, 409].includes(e.response?.status) && e.response?.data?.code !== 10009)
      sessionStorage.removeItem(storage)
    throw e
  }
}

export const getOrder = (no, ops = false) =>
  request.get((ops ? '/ops' : '') + '/orders/' + no + '/')
export const getOrders = (ops, params) => request.get((ops ? '/ops' : '') + '/orders/', { params })
export const statusNames = {
  pending: '待付款',
  paid: '待发货',
  shipped: '待收货',
  completed: '已完成',
  canceled: '已取消',
}
