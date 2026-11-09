import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { publishContent } from './cms'

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

it('retries a lost CMS publication with the same version and key', async () => {
  const content = { id: '7', version: 3, published_revision: null, latest_revision: { revision_no: 2 } }
  request.post.mockRejectedValueOnce(new Error('timeout'))
  await expect(publishContent(content, 'publish', '发布')).rejects.toThrow('timeout')
  const original = request.post.mock.calls[0]
  expect(original[1]).toEqual({ revision: 2, expected_version: 3, reason: '发布' })
  request.post.mockResolvedValueOnce({ publication_state: 'online' })
  await publishContent(content, 'publish', '发布')
  expect(request.post.mock.calls[1]).toEqual(original)
  expect(sessionStorage.getItem('siq.cms.42.publish.7.3.2')).toBeNull()
})
