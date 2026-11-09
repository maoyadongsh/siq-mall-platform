import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { updateUserRoles } from './operations'

vi.mock('@/utils/request', () => ({ default: { post: vi.fn() } }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({ profile: { id: '42' } }) }))
beforeEach(() => {
  const store = new Map()
  vi.stubGlobal('sessionStorage', {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
    removeItem: (key) => store.delete(key),
  })
  request.post.mockReset()
})
afterEach(() => vi.unstubAllGlobals())

it('replays role assignment with the original user version and key', async () => {
  const user = { id: '8', expected_version: 2 }
  request.post.mockRejectedValueOnce(new Error('offline'))
  await expect(updateUserRoles(user, [3], '授权')).rejects.toThrow('offline')
  const original = request.post.mock.calls[0]
  request.post.mockResolvedValueOnce({ expected_version: 3 })
  await updateUserRoles(user, [3], '授权')
  expect(request.post.mock.calls[1]).toEqual(original)
  expect(sessionStorage.getItem('siq.roles.42.8.2')).toBeNull()
})
