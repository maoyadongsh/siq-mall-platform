import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { updateUserRoles } from './operations'

vi.mock('@/utils/request', () => ({ default: { post: vi.fn() } }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({ profile: { id: '42' } }) }))

const post = vi.mocked(request.post)

beforeEach(() => {
  const store = new Map<string, string>()
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
  })
  post.mockReset()
})
afterEach(() => vi.unstubAllGlobals())

it('replays role assignment with the original user version and key', async () => {
  const user = { id: '8', expected_version: 2 }
  post.mockRejectedValueOnce(new Error('offline'))
  await expect(updateUserRoles(user, [3], '授权')).rejects.toThrow('offline')
  const original = post.mock.calls[0]
  post.mockResolvedValueOnce({ expected_version: 3 })
  await updateUserRoles(user, [3], '授权')
  expect(post.mock.calls[1]).toEqual(original)
  expect(sessionStorage.getItem('siq.roles.42.8.2')).toBeNull()
})
