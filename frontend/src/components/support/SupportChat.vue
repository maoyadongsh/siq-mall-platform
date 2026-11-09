<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  closeConversation,
  getConversation,
  getMessages,
  readConversation,
  sendChatMessage,
} from '@/api/support'
import './support.css'

const props = defineProps({ conversationId: { type: String, required: true }, ops: Boolean })
const emit = defineEmits(['new-conversation', 'changed'])
const conversation = ref(null)
const messages = ref([])
const pending = ref([])
const draft = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const olderCursor = ref(null)
const pollCursor = ref(null)
const hasMore = ref(false)
const closeReason = ref('问题已解决')
let timer

function syncCursors(data, older = false) {
  if (older) {
    olderCursor.value = data.next_cursor
    hasMore.value = data.has_more
    if (!pollCursor.value && data.poll_cursor) pollCursor.value = data.poll_cursor
    return
  }
  if (data.poll_cursor) pollCursor.value = data.poll_cursor
  if (data.next_cursor) pollCursor.value = data.next_cursor
}
function appendUnique(incoming, prepend = false) {
  const known = new Set(messages.value.map((row) => row.id))
  const fresh = incoming.filter((row) => !known.has(row.id))
  messages.value = prepend ? [...fresh, ...messages.value] : [...messages.value, ...fresh]
}
async function refreshConversation() {
  conversation.value = await getConversation(props.conversationId, props.ops)
  emit('changed', conversation.value)
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
    error.value = e.message
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
      direction: 'newer', cursor: pollCursor.value, limit: 100,
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
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function send(item) {
  item.state = item.state === 'failed' ? 'retrying' : 'sending'
  error.value = ''
  try {
    const result = await sendChatMessage(props.conversationId, {
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
    item.retryable = !e.response || e.response.status >= 500
    error.value = e.response ? e.message : `${e.message}；发送结果待确认，可用原消息标识重试。`
  }
}
function submitMessage() {
  const body = draft.value.trim()
  if (!body || busy.value || conversation.value?.status !== 'open') return
  const item = { client_message_id: crypto.randomUUID(), body, state: 'sending', retryable: true }
  pending.value.push(item)
  send(item)
}
async function close() {
  if (busy.value || !closeReason.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    conversation.value = await closeConversation(conversation.value, closeReason.value.trim(), props.ops)
    notice.value = '会话已关闭，之后不能再发送消息。'
    await refreshConversation()
  } catch (e) {
    error.value = e.response ? e.message : `${e.message}；结果待确认，请重试或刷新核对。`
  } finally {
    busy.value = false
  }
}
function visibility() {
  if (document.visibilityState === 'visible') poll()
}
onMounted(() => {
  initialLoad()
  timer = setInterval(poll, 5000)
  document.addEventListener('visibilitychange', visibility)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', visibility)
})
</script>

<template>
  <section class="support-chat">
    <div class="support-chat__heading"><div><h2>客服会话 #{{ conversationId }}</h2><p v-if="conversation">{{ conversation.status === 'open' ? '会话进行中' : '会话已关闭' }}<span v-if="conversation.assigned_agent_display_name"> · 接待客服 {{ conversation.assigned_agent_display_name }}</span></p></div><button v-if="conversation?.status === 'open'" :disabled="busy" @click="close">关闭会话</button><button v-else-if="!ops" @click="emit('new-conversation')">新开会话</button></div>
    <p v-if="error" role="alert" class="support-error">{{ error }}</p><p v-if="notice" role="status" class="support-success">{{ notice }}</p>
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
