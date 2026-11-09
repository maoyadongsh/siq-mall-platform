import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const prefix = (ops) => (ops ? '/ops/conversations' : '/conversations')
export const listConversations = (params, ops = false) =>
  request.get(`${prefix(ops)}/`, { params })
export const getConversation = (id, ops = false) => request.get(`${prefix(ops)}/${id}/`)
export const getMessages = (id, params, ops = false) =>
  request.get(`${prefix(ops)}/${id}/messages/`, { params })
export const sendChatMessage = (id, message, ops = false) =>
  request.post(`${prefix(ops)}/${id}/messages/`, message, {
    headers: { 'Idempotency-Key': message.client_message_id },
  })
export const readConversation = (id, messageId, ops = false) =>
  request.post(`${prefix(ops)}/${id}/read/`, { last_message_id: messageId })

function write(storage, path, data) {
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post(path, data, { headers: { 'Idempotency-Key': key } })
    .then((result) => {
      sessionStorage.removeItem(storage)
      return result
    })
    .catch((error) => {
      if ([400, 403, 404, 409].includes(error.response?.status)) sessionStorage.removeItem(storage)
      throw error
    })
}

export function createConversation(data = {}) {
  const userId = useUserStore().profile.id
  return write(`siq.support.create.${userId}.${data.order_no || 'general'}`, '/conversations/', data)
}
export function closeConversation(conversation, reason, ops = false) {
  const userId = useUserStore().profile.id
  return write(
    `siq.support.close.${userId}.${conversation.id}.${conversation.version}`,
    `${prefix(ops)}/${conversation.id}/close/`,
    { reason },
  )
}
export function assignConversation(conversation, agentId, reason = '') {
  const userId = useUserStore().profile.id
  return write(
    `siq.support.assign.${userId}.${conversation.id}.${conversation.version}.${agentId}`,
    `/ops/conversations/${conversation.id}/assign/`,
    { agent_id: Number(agentId), expected_version: conversation.version, reason },
  )
}
