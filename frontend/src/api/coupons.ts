import type { Coupon } from '@/types/models'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export function offer(c: Coupon): string {
  const benefit =
    c.type === 'fixed'
      ? '减 ¥' + c.reduction_amount
      : '减免 ' + (c.discount_bps ?? 0) / 100 + '%，最高 ¥' + c.cap_amount
  return Number(c.threshold_amount) > 0 ? '满 ¥' + c.threshold_amount + ' ' + benefit : benefit
}

export const stateName: Record<string, string> = {
  draft: '草稿',
  active: '发放中',
  stopped: '已停领',
  unused: '未使用',
  reserved: '订单占用中',
  used: '已核销',
  expired: '已过期',
}

export async function couponAction<T = Coupon>(
  id: string,
  action: string,
  data: Record<string, unknown> = {},
): Promise<T> {
  const account = useUserStore().profile?.id
  const slot = 'siq.coupon.' + account + '.' + id + '.' + action
  const existing = JSON.parse(sessionStorage.getItem(slot) || 'null') as {
    key: string
    data: Record<string, unknown>
  } | null
  const op = existing || { key: crypto.randomUUID(), data }
  sessionStorage.setItem(slot, JSON.stringify(op))
  try {
    const base = action === 'claim' ? '/coupons/' : '/ops/coupons/'
    const result = await request.post<T>(base + id + '/' + action + '/', op.data, {
      headers: { 'Idempotency-Key': op.key },
    })
    sessionStorage.removeItem(slot)
    return result
  } catch (e) {
    const error = e as { response?: { status: number } }
    if ([400, 403, 404, 409].includes(error.response?.status ?? 0)) sessionStorage.removeItem(slot)
    throw e
  }
}
