import type { ChatMessage, Conversation, Page, ReadResult, SupportHistory } from '@/types/models'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const prefix = (ops: boolean) => (ops ? '/ops/conversations' : '/conversations')

export interface WsTicket {
  ticket: string
  expires_in: number
  heartbeat_seconds: number
  path: string
}

export const createWsTicket = (conversationId: string, ops = false): Promise<WsTicket> =>
  request.post(`${prefix(ops)}/ws-ticket/`, { conversation_id: Number(conversationId) })

export const listConversations = (
  params?: Record<string, string | number | undefined>,
  ops = false,
): Promise<Page<Conversation>> => request.get(`${prefix(ops)}/`, { params })

export const getConversation = (id: string, ops = false): Promise<Conversation> =>
  request.get(`${prefix(ops)}/${id}/`)

export const getMessages = (
  id: string,
  params: Record<string, string | number | undefined>,
  ops = false,
): Promise<SupportHistory> => request.get(`${prefix(ops)}/${id}/messages/`, { params })

export const sendChatMessage = (
  id: string,
  message: { client_message_id: string; body: string },
  ops = false,
): Promise<ChatMessage> =>
  request.post(`${prefix(ops)}/${id}/messages/`, message, {
    headers: { 'Idempotency-Key': message.client_message_id },
  })

export const readConversation = (
  id: string,
  messageId: string,
  ops = false,
): Promise<ReadResult> => request.post(`${prefix(ops)}/${id}/read/`, { last_message_id: messageId })

function write<T>(storage: string, path: string, data: Record<string, unknown>): Promise<T> {
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post<T>(path, data, { headers: { 'Idempotency-Key': key } })
    .then((result) => {
      sessionStorage.removeItem(storage)
      return result
    })
    .catch((error: { response?: { status: number } }) => {
      if ([400, 403, 404, 409].includes(error.response?.status ?? 0))
        sessionStorage.removeItem(storage)
      throw error
    })
}

export function createConversation(data: { order_no?: string } = {}): Promise<Conversation> {
  const userId = useUserStore().profile?.id
  return write<Conversation>(
    `siq.support.create.${userId}.${data.order_no || 'general'}`,
    '/conversations/',
    data,
  )
}

export function closeConversation(
  conversation: Pick<Conversation, 'id' | 'version'>,
  reason: string,
  ops = false,
): Promise<Conversation> {
  const userId = useUserStore().profile?.id
  return write<Conversation>(
    `siq.support.close.${userId}.${conversation.id}.${conversation.version}`,
    `${prefix(ops)}/${conversation.id}/close/`,
    { reason },
  )
}

export function assignConversation(
  conversation: Pick<Conversation, 'id' | 'version'>,
  agentId: string | number,
  reason = '',
): Promise<Conversation> {
  const userId = useUserStore().profile?.id
  return write<Conversation>(
    `siq.support.assign.${userId}.${conversation.id}.${conversation.version}.${agentId}`,
    `/ops/conversations/${conversation.id}/assign/`,
    { agent_id: Number(agentId), expected_version: conversation.version, reason },
  )
}
