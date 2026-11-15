import { beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { closeConversation, createWsTicket, sendChatMessage } from './support'

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

it('uses the same client id and idempotency key for a network retry', async () => {
  const message = { client_message_id: crypto.randomUUID(), body: '弱网重试' }
  post.mockRejectedValueOnce(new Error('offline'))
  await expect(sendChatMessage('8', message)).rejects.toThrow('offline')
  const original = post.mock.calls[0]
  post.mockResolvedValueOnce({ id: '9' })
  await sendChatMessage('8', message)
  expect(post.mock.calls[1]).toEqual(original)
  expect((original[2]?.headers as Record<string, string>)['Idempotency-Key']).toBe(
    message.client_message_id,
  )
})

it('keeps the original close key after an unknown result', async () => {
  const conversation = { id: '8', version: 3 }
  post.mockRejectedValueOnce(new Error('offline'))
  await expect(closeConversation(conversation, '结束')).rejects.toThrow('offline')
  const original = post.mock.calls[0]
  post.mockResolvedValueOnce({ status: 'closed' })
  await closeConversation(conversation, '结束')
  expect(post.mock.calls[1]).toEqual(original)
})

it('requests a one-time websocket ticket for the conversation', async () => {
  post.mockResolvedValueOnce({
    ticket: 't',
    expires_in: 60,
    heartbeat_seconds: 25,
    path: '/ws/support/8/',
  })
  const ticket = await createWsTicket('8')
  expect(post).toHaveBeenCalledWith('/conversations/ws-ticket/', { conversation_id: 8 })
  expect(ticket.path).toBe('/ws/support/8/')
})
