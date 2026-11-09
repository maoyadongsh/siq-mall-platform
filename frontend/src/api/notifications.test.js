import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { activateTemplate, readNotifications, targetPath } from './notifications'

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

it('replays template activation with the original key after an unknown result', async () => {
  const row = { id: '8', version: 2 }
  request.post.mockRejectedValueOnce(new Error('timeout'))
  await expect(activateTemplate(row, 1)).rejects.toThrow('timeout')
  const original = request.post.mock.calls[0]
  request.post.mockResolvedValueOnce({ active: true })
  await activateTemplate(row, 1)
  expect(request.post.mock.calls[1]).toEqual(original)
  expect(sessionStorage.getItem('siq.notification.template.42.8.2')).toBeNull()
})

it('uses the server-issued read watermark and maps only known business targets', async () => {
  request.post.mockResolvedValue({ total: 0 })
  await readNotifications({ watermark: 'signed', type: 'order' })
  expect(request.post).toHaveBeenCalledWith('/notifications/read/', {
    watermark: 'signed',
    type: 'order',
  })
  expect(targetPath({ target_type: 'order', target_id: 'a/b' })).toBe('/orders/a%2Fb')
  expect(targetPath({ target_type: 'javascript', target_id: 'alert(1)' })).toBe('')
})
