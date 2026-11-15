<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  closeConversation,
  createWsTicket,
  getConversation,
  getMessages,
  readConversation,
  sendChatMessage,
  type WsTicket,
} from '@/api/support'
import type { ChatMessage, Conversation, PendingMessage, SupportHistory } from '@/types/models'
import { messageOf, statusOf } from '@/utils/errors'
import './support.css'

type SentMessage = ChatMessage & { poll_cursor?: string | null }

const props = defineProps({ conversationId: { type: String, required: true }, ops: Boolean })
const emit = defineEmits<{
  (e: 'new-conversation'): void
  (e: 'changed', conversation: Conversation): void
}>()
const conversation = ref<Conversation | null>(null)
const messages = ref<ChatMessage[]>([])
const pending = ref<PendingMessage[]>([])
const draft = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const olderCursor = ref<string | null>(null)
const pollCursor = ref<string | null>(null)
const hasMore = ref(false)
const closeReason = ref('问题已解决')
const socketState = ref<'off' | 'connecting' | 'open' | 'waiting'>('off')
let timer: ReturnType<typeof setInterval> | undefined
let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | undefined
let heartbeatTimer: ReturnType<typeof setInterval> | undefined
let heartbeatMs = 25000
let lastSocketAt = 0
let attempts = 0
let closedByUs = false

function syncCursors(data: SupportHistory, older = false) {
  if (older) {
    olderCursor.value = data.next_cursor
    hasMore.value = data.has_more
    if (!pollCursor.value && data.poll_cursor) pollCursor.value = data.poll_cursor
    return
  }
  if (data.poll_cursor) pollCursor.value = data.poll_cursor
  if (data.next_cursor) pollCursor.value = data.next_cursor
}
function appendUnique(incoming: ChatMessage[], prepend = false) {
  const known = new Set(messages.value.map((row) => row.id))
  const fresh = incoming.filter((row) => !known.has(row.id))
  messages.value = prepend ? [...fresh, ...messages.value] : [...messages.value, ...fresh]
}
async function refreshConversation() {
  const data = await getConversation(props.conversationId, props.ops)
  conversation.value = data
  emit('changed', data)
}
async function markLatest() {
  const latest = messages.value[messages.value.length - 1]
  if (latest) await readConversation(props.conversationId, latest.id, props.ops)
}
async function initialLoad() {
  loading.value = true
  error.value = ''
  try {
    await refreshConversation()
    const data = await getMessages(props.conversationId, { limit: 20, direction: 'older' }, props.ops)
    messages.value = data.results
    syncCursors(data, true)
    await markLatest()
    await refreshConversation()
  } catch (e) {
    error.value = messageOf(e)
  } finally {
    loading.value = false
  }
}
async function poll() {
  if (document.visibilityState !== 'visible' || busy.value || conversation.value?.status !== 'open') return
  try {
    if (!pollCursor.value) {
      const latest = await getMessages(props.conversationId, { limit: 1, direction: 'older' }, props.ops)
      syncCursors(latest, true)
      if (!latest.poll_cursor) {
        await refreshConversation()
        return
      }
    }
    const data = await getMessages(props.conversationId, {
      direction: 'newer', cursor: pollCursor.value ?? undefined, limit: 100,
    }, props.ops)
    if (data.results.length) {
      appendUnique(data.results)
      await markLatest()
    }
    syncCursors(data)
    await refreshConversation()
  } catch {
    return
  }
}
async function loadOlder() {
  if (!olderCursor.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await getMessages(props.conversationId, {
      direction: 'older', cursor: olderCursor.value, limit: 20,
    }, props.ops)
    appendUnique(data.results, true)
    syncCursors(data, true)
  } catch (e) {
    error.value = messageOf(e)
  } finally {
    loading.value = false
  }
}
async function send(item: PendingMessage) {
  item.state = item.state === 'failed' ? 'retrying' : 'sending'
  error.value = ''
  try {
    const result: SentMessage = await sendChatMessage(props.conversationId, {
      client_message_id: item.client_message_id, body: item.body,
    }, props.ops)
    appendUnique([result])
    pending.value = pending.value.filter((row) => row.client_message_id !== item.client_message_id)
    if (draft.value === item.body) draft.value = ''
    pollCursor.value = result.poll_cursor || pollCursor.value
    await poll()
    await refreshConversation()
  } catch (e) {
    item.state = 'failed'
    const status = statusOf(e)
    item.retryable = status === undefined || status >= 500
    error.value = status === undefined
      ? `${messageOf(e)}；发送结果待确认，可用原消息标识重试。`
      : messageOf(e)
  }
}
function submitMessage() {
  const body = draft.value.trim()
  if (!body || busy.value || conversation.value?.status !== 'open') return
  const item: PendingMessage = { client_message_id: crypto.randomUUID(), body, state: 'sending', retryable: true }
  pending.value.push(item)
  send(item)
}
async function close() {
  if (busy.value || !closeReason.value.trim() || !conversation.value) return
  busy.value = true
  error.value = ''
  try {
    conversation.value = await closeConversation(conversation.value, closeReason.value.trim(), props.ops)
    notice.value = '会话已关闭，之后不能再发送消息。'
    await refreshConversation()
  } catch (e) {
    error.value = statusOf(e) === undefined
      ? `${messageOf(e)}；结果待确认，请重试或刷新核对。`
      : messageOf(e)
  } finally {
    busy.value = false
  }
}
function socketUrl(ticket: WsTicket): string {
  const configured = import.meta.env.VITE_WS_BASE_URL
  const base = configured
    ? configured.replace(/\/$/, '')
    : `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`
  return `${base}${ticket.path}`
}
function stopHeartbeat() {
  clearInterval(heartbeatTimer)
  heartbeatTimer = undefined
}
function startHeartbeat() {
  stopHeartbeat()
  lastSocketAt = Date.now()
  heartbeatTimer = setInterval(() => {
    if (Date.now() - lastSocketAt > heartbeatMs * 2) {
      socket?.close()
      return
    }
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' }))
  }, heartbeatMs)
}
function stopSocket() {
  closedByUs = true
  clearTimeout(reconnectTimer)
  reconnectTimer = undefined
  stopHeartbeat()
  if (socket) {
    socket.onclose = null
    socket.close(1000)
    socket = null
  }
  socketState.value = 'off'
}
function scheduleReconnect() {
  if (closedByUs || document.visibilityState !== 'visible') return
  if (conversation.value?.status !== 'open') return
  if (attempts >= 5) {
    socketState.value = 'off'
    return
  }
  const delay = Math.min(1000 * 2 ** attempts, 30000)
  attempts += 1
  clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(connectSocket, delay)
}
function handleSocket(payload: { type?: string; message?: ChatMessage }) {
  lastSocketAt = Date.now()
  if (payload.type === 'message' && payload.message) {
    appendUnique([payload.message])
    markLatest().catch(() => undefined)
    refreshConversation().catch(() => undefined)
    return
  }
  if (payload.type === 'closed') {
    notice.value = '会话已关闭，之后不能再发送消息。'
    refreshConversation().catch(() => undefined)
    stopSocket()
  }
}
async function connectSocket() {
  if (closedByUs || socket || socketState.value === 'connecting') return
  if (document.visibilityState !== 'visible' || conversation.value?.status !== 'open') return
  socketState.value = 'connecting'
  try {
    const ticket = await createWsTicket(props.conversationId, props.ops)
    if (closedByUs || document.visibilityState !== 'visible') {
      socketState.value = 'off'
      return
    }
    heartbeatMs = ticket.heartbeat_seconds * 1000
    const ws = new WebSocket(socketUrl(ticket), [`support.ticket.${ticket.ticket}`])
    socket = ws
    ws.onopen = () => {
      if (socket !== ws) return
      attempts = 0
      socketState.value = 'open'
      startHeartbeat()
      ensurePolling()
    }
    ws.onmessage = (event) => {
      if (socket !== ws) return
      try {
        handleSocket(JSON.parse(String(event.data)) as { type?: string; message?: ChatMessage })
      } catch {
        return
      }
    }
    ws.onerror = () => {
      if (socket === ws) ws.close()
    }
    ws.onclose = () => {
      if (socket !== ws) return
      socket = null
      stopHeartbeat()
      if (closedByUs) return
      socketState.value = 'waiting'
      ensurePolling()
      scheduleReconnect()
    }
  } catch {
    socketState.value = 'off'
    scheduleReconnect()
  }
}
function ensurePolling() {
  clearInterval(timer)
  // WebSocket 只负责降低延迟；轮询始终保留，避免静默断线时长时间收不到消息。
  timer = setInterval(poll, 5000)
}
function visibility() {
  if (document.visibilityState === 'visible') {
    poll()
    if (!socket && conversation.value?.status === 'open') {
      closedByUs = false
      connectSocket()
    }
  } else {
    if (socket) {
      socket.onclose = null
      socket.close(1000)
      socket = null
    }
    stopHeartbeat()
    clearTimeout(reconnectTimer)
    socketState.value = 'off'
  }
}
function restartRealtime() {
  stopSocket()
  closedByUs = false
  attempts = 0
  ensurePolling()
  if (conversation.value?.status === 'open') connectSocket()
}
onMounted(() => {
  initialLoad().then(() => connectSocket())
  ensurePolling()
  document.addEventListener('visibilitychange', visibility)
})
onBeforeUnmount(() => {
  stopSocket()
  clearInterval(timer)
  document.removeEventListener('visibilitychange', visibility)
})
watch(
  () => props.conversationId,
  () => {
    messages.value = []
    pending.value = []
    olderCursor.value = null
    pollCursor.value = null
    hasMore.value = false
    notice.value = ''
    initialLoad().then(() => restartRealtime())
  },
)
</script>

<template>
  <section class="support-chat">
    <div class="support-chat__heading"><div><h2>客服会话 #{{ conversationId }}</h2><p v-if="conversation">{{ conversation.status === 'open' ? '会话进行中' : '会话已关闭' }}<span v-if="conversation.assigned_agent_display_name"> · 接待客服 {{ conversation.assigned_agent_display_name }}</span></p></div><button v-if="conversation?.status === 'open'" :disabled="busy" @click="close">关闭会话</button><button v-else-if="!ops" @click="emit('new-conversation')">新开会话</button></div>
    <p v-if="error" role="alert" class="support-error">{{ error }}</p><p v-if="notice" role="status" class="support-success">{{ notice }}</p>
    <p v-if="socketState === 'waiting'" role="status" class="support-empty">实时连接中断，正在重连；消息会继续通过轮询接收。</p>
    <p v-if="loading && !messages.length">正在读取会话…</p>
    <button v-if="hasMore" :disabled="loading" @click="loadOlder">加载更早消息</button>
    <div class="support-chat__messages" aria-live="polite">
      <p v-if="!loading && !messages.length && !pending.length" class="support-empty">还没有消息，请描述你的问题。</p>
      <article v-for="row in messages" :key="row.id" :class="['support-message', { own: (row.sender_role === 'agent') === ops }]">
        <small>{{ row.sender_role === 'buyer' ? '买家' : '客服' }} · {{ new Date(row.created_at).toLocaleString() }}</small>
        <p>{{ row.body }}</p>
        <small v-if="(row.sender_role === 'agent') === ops">{{ Number(conversation?.counterpart_read_seq || 0) >= Number(row.conversation_seq) ? '对方已读' : '未读' }}</small>
      </article>
      <article v-for="item in pending" :key="item.client_message_id" class="support-message own pending">
        <small>{{ { sending: '发送中', failed: '发送失败', retrying: '重试中' }[item.state] }}</small><p>{{ item.body }}</p>
        <button v-if="item.state === 'failed' && item.retryable" @click="send(item)">重试发送</button>
      </article>
    </div>
    <form v-if="conversation?.status === 'open'" class="support-chat__composer" @submit.prevent="submitMessage">
      <label for="support-draft">消息内容</label><textarea id="support-draft" v-model="draft" rows="3" maxlength="2000" placeholder="请输入1–2000字纯文本" />
      <button :disabled="!draft.trim()">发送消息</button>
    </form>
    <p v-else class="support-empty">此会话已关闭，历史仍可查看；继续咨询请新开会话。</p>
    <aside v-if="ops && conversation" class="support-order"><h3>买家</h3><p>{{ conversation.buyer_display_name }}</p><p>不显示推测的在线状态或非必要收货信息。</p></aside>
    <aside v-if="conversation?.order_summary" class="support-order"><h3>关联订单</h3><p>{{ conversation.order_summary.order_no }} · {{ conversation.order_summary.status }} · ¥{{ conversation.order_summary.payable_amount }}</p><ul><li v-for="(item, index) in conversation.order_summary.items" :key="index">{{ item.title }} × {{ item.quantity }}</li></ul></aside>
    <label v-if="conversation?.status === 'open'" class="support-close-reason">关闭原因<input v-model="closeReason" maxlength="100"></label>
  </section>
</template>
