import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const reviewStatuses = {
  pending: '待审核',
  approved: '已公开',
  rejected: '未通过',
  hidden: '已隐藏',
}

async function write(path, scope, data) {
  const storage = 'siq.review.' + useUserStore().profile.id + '.' + scope
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  try {
    const result = await request.post(path, data, { headers: { 'Idempotency-Key': key } })
    sessionStorage.removeItem(storage)
    return result
  } catch (e) {
    if ([400, 403, 404, 409].includes(e.response?.status)) sessionStorage.removeItem(storage)
    throw e
  }
}
export function submitReview(itemId, rating, content) {
  return write('/reviews/', 'submit.' + itemId, { order_item_id: itemId, rating, content })
}
export function moderateReview(review, action, reason) {
  return write(
    '/ops/reviews/' + review.id + '/moderate/',
    'moderate.' + review.id + '.' + review.version,
    { action, reason, expected_version: review.version },
  )
}
export const mine = (params) => request.get('/users/me/reviews/', { params })
export const publicReviews = (id, page) =>
  request.get('/products/' + id + '/reviews/', { params: { page } })
export const queue = (params) => request.get('/ops/reviews/', { params })
