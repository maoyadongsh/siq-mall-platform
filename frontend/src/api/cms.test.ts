import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { publishContent } from './cms'

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

it('retries a lost CMS publication with the same version and key', async () => {
  const content = { id: '7', version: 3, published_revision: null, latest_revision: { revision_no: 2 } }
  post.mockRejectedValueOnce(new Error('timeout'))
  await expect(publishContent(content, 'publish', '发布')).rejects.toThrow('timeout')
  const original = post.mock.calls[0]
  expect(original[1]).toEqual({ revision: 2, expected_version: 3, reason: '发布' })
  post.mockResolvedValueOnce({ publication_state: 'online' })
  await publishContent(content, 'publish', '发布')
  expect(post.mock.calls[1]).toEqual(original)
  expect(sessionStorage.getItem('siq.cms.42.publish.7.3.2')).toBeNull()
})
