import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import request from '@/utils/request'
import { submitReview, moderateReview } from './reviews'

vi.mock('@/utils/request', () => ({ default: { post: vi.fn() } }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({ profile: { id: '42' } }) }))

beforeEach(() => {
  const store = new Map()
  vi.stubGlobal('sessionStorage', {
    getItem: (k) => store.get(k) ?? null,
    setItem: (k, v) => store.set(k, v),
    removeItem: (k) => store.delete(k),
  })
  request.post.mockReset()
})
afterEach(() => vi.unstubAllGlobals())

it('recovers a lost submission using the original key, without storing review text', async () => {
  request.post.mockRejectedValueOnce(new Error('timeout'))
  await expect(submitReview('12', 1, '这款偏小')).rejects.toThrow('timeout')
  const original = request.post.mock.calls[0]
  expect(sessionStorage.getItem('siq.review.42.submit.12')).toBe(
    original[2].headers['Idempotency-Key'],
  )
  request.post.mockResolvedValueOnce({ status: 'pending' })
  await submitReview('12', 1, '这款偏小')
  expect(request.post.mock.calls[1]).toEqual(original)
  expect(sessionStorage.getItem('siq.review.42.submit.12')).toBeNull()
})
it('makes a new moderation decision with its reviewed version after a confirmed conflict', async () => {
  request.post.mockRejectedValueOnce({ response: { status: 409 } })
  await expect(moderateReview({ id: '12', version: 1 }, 'approve', '')).rejects.toBeDefined()
  request.post.mockResolvedValueOnce({ status: 'hidden' })
  await moderateReview({ id: '12', version: 2 }, 'hide', '含私人信息')
  const [first, second] = request.post.mock.calls
  expect(second[1]).toEqual({ action: 'hide', reason: '含私人信息', expected_version: 2 })
  expect(second[2].headers['Idempotency-Key']).not.toBe(first[2].headers['Idempotency-Key'])
})
