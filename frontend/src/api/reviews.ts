import type { Page, PublicReviewPage, ReviewRow } from '@/types/models'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const reviewStatuses: Record<string, string> = {
  pending: '待审核',
  approved: '已公开',
  rejected: '未通过',
  hidden: '已隐藏',
}

export interface ReviewRecord {
  id: string
  order_item_id: string
  order_no: string
  product_id: string
  product_title: string
  sku_label: string
  rating: number
  content: string
  created_at: string
  status: string
  version: number
  moderation_reason: string
}

async function write<T>(path: string, scope: string, data: Record<string, unknown>): Promise<T> {
  const storage = 'siq.review.' + useUserStore().profile?.id + '.' + scope
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  try {
    const result = await request.post<T>(path, data, { headers: { 'Idempotency-Key': key } })
    sessionStorage.removeItem(storage)
    return result
  } catch (e) {
    const error = e as { response?: { status: number } }
    if ([400, 403, 404, 409].includes(error.response?.status ?? 0)) sessionStorage.removeItem(storage)
    throw e
  }
}

export function submitReview(
  itemId: string,
  rating: number,
  content: string,
): Promise<ReviewRecord> {
  return write('/reviews/', 'submit.' + itemId, { order_item_id: itemId, rating, content })
}

export function moderateReview(
  review: Pick<ReviewRow, 'id' | 'version'>,
  action: string,
  reason: string,
): Promise<ReviewRecord> {
  return write(
    '/ops/reviews/' + review.id + '/moderate/',
    'moderate.' + review.id + '.' + review.version,
    { action, reason, expected_version: review.version },
  )
}

export const mine = (params?: Record<string, string | number | undefined>): Promise<Page<ReviewRow>> =>
  request.get('/users/me/reviews/', { params })

export const publicReviews = (id: string, page: number): Promise<PublicReviewPage> =>
  request.get('/products/' + id + '/reviews/', { params: { page } })

export const queue = (params?: Record<string, string | number | undefined>): Promise<Page<ReviewRow>> =>
  request.get('/ops/reviews/', { params })
