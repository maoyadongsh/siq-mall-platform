import { beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { closeConversation, sendChatMessage } from './support'

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

it('uses the same client id and idempotency key for a network retry', async () => {
  const message = { client_message_id: crypto.randomUUID(), body: '弱网重试' }
  request.post.mockRejectedValueOnce(new Error('offline'))
  await expect(sendChatMessage('8', message)).rejects.toThrow('offline')
  const original = request.post.mock.calls[0]
  request.post.mockResolvedValueOnce({ id: '9' })
  await sendChatMessage('8', message)
  expect(request.post.mock.calls[1]).toEqual(original)
  expect(original[2].headers['Idempotency-Key']).toBe(message.client_message_id)
})

it('keeps the original close key after an unknown result', async () => {
  const conversation = { id: '8', version: 3 }
  request.post.mockRejectedValueOnce(new Error('offline'))
  await expect(closeConversation(conversation, '结束')).rejects.toThrow('offline')
  const original = request.post.mock.calls[0]
  request.post.mockResolvedValueOnce({ status: 'closed' })
  await closeConversation(conversation, '结束')
  expect(request.post.mock.calls[1]).toEqual(original)
})
