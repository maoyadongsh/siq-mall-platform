import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import request from '@/utils/request'
import { submitReview, moderateReview } from './reviews'

vi.mock('@/utils/request', () => ({ default: { post: vi.fn() } }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({ profile: { id: '42' } }) }))

const post = vi.mocked(request.post)

beforeEach(() => {
  const store = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, v),
    removeItem: (k: string) => store.delete(k),
  })
  post.mockReset()
})
afterEach(() => vi.unstubAllGlobals())

it('recovers a lost submission using the original key, without storing review text', async () => {
  post.mockRejectedValueOnce(new Error('timeout'))
  await expect(submitReview('12', 1, '这款偏小')).rejects.toThrow('timeout')
  const original = post.mock.calls[0]
  expect(sessionStorage.getItem('siq.review.42.submit.12')).toBe(
    (original[2]?.headers as Record<string, string>)['Idempotency-Key'],
  )
  post.mockResolvedValueOnce({ status: 'pending' })
  await submitReview('12', 1, '这款偏小')
  expect(post.mock.calls[1]).toEqual(original)
  expect(sessionStorage.getItem('siq.review.42.submit.12')).toBeNull()
})

it('makes a new moderation decision with its reviewed version after a confirmed conflict', async () => {
  post.mockRejectedValueOnce({ response: { status: 409 } })
  await expect(moderateReview({ id: '12', version: 1 }, 'approve', '')).rejects.toBeDefined()
  post.mockResolvedValueOnce({ status: 'hidden' })
  await moderateReview({ id: '12', version: 2 }, 'hide', '含私人信息')
  const [first, second] = post.mock.calls
  expect(second[1]).toEqual({ action: 'hide', reason: '含私人信息', expected_version: 2 })
  expect((second[2]?.headers as Record<string, string>)['Idempotency-Key']).not.toBe(
    (first[2]?.headers as Record<string, string>)['Idempotency-Key'],
  )
})
