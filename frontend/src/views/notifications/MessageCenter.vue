<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  listNotifications,
  notificationTypes,
  readNotifications,
  targetPath,
  unreadNotifications,
} from '@/api/notifications'
import './messages.css'

const router = useRouter()
const rows = ref([])
const type = ref('')
const counts = ref({ total: 0, by_type: {} })
const cursor = ref(null)
const hasMore = ref(false)
const watermark = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
let requestSeq = 0

function changed() {
  window.dispatchEvent(new Event('siq:notifications-changed'))
}

async function refreshCount() {
  counts.value = await unreadNotifications()
}

async function load(append = false) {
  const ticket = ++requestSeq
  loading.value = true
  error.value = ''
  if (!append) cursor.value = null
  try {
    const data = await listNotifications({
      type: type.value || undefined,
      cursor: cursor.value || undefined,
      limit: 20,
    })
    if (ticket !== requestSeq) return
    rows.value = append ? [...rows.value, ...data.results] : data.results
    cursor.value = data.next_cursor
    hasMore.value = data.has_more
    watermark.value = data.read_watermark
    await refreshCount()
  } catch (e) {
    if (ticket === requestSeq) error.value = e.message
  } finally {
    if (ticket === requestSeq) loading.value = false
  }
}

async function selectType(value) {
  if (busy.value || type.value === value) return
  type.value = value
  notice.value = ''
  await load()
}

async function markAll() {
  if (busy.value || !watermark.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await readNotifications({
      watermark: watermark.value,
      type: type.value || undefined,
    })
    notice.value = `已处理 ${result.updated_count} 条消息；新到消息仍会保持未读。`
    changed()
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function open(row) {
  if (busy.value) return
  const path = targetPath(row)
  if (!path) {
    error.value = '这条消息关联的内容已不可用，请返回消息列表。'
    return
  }
  busy.value = true
  error.value = ''
  try {
    if (!row.is_read) {
      await readNotifications({ ids: [row.id] })
      row.is_read = true
      changed()
      await refreshCount()
    }
    await router.push(path)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="message-center">
    <div class="message-center__heading">
      <div>
        <h1>消息中心</h1>
        <p>订单、客服与系统消息在这里留存，点击后再标记为已读。</p>
      </div>
      <button :disabled="busy || loading || !counts.total" @click="markAll">全部已读</button>
    </div>
    <div class="message-center__tabs" aria-label="消息分类">
      <button :aria-pressed="type === ''" @click="selectType('')">
        全部 {{ counts.total || '' }}
      </button>
      <button
        v-for="(label, key) in notificationTypes"
        :key="key"
        :aria-pressed="type === key"
        @click="selectType(key)"
      >
        {{ label }} {{ counts.by_type?.[key] || '' }}
      </button>
    </div>
    <p v-if="notice" role="status" class="message-center__success">{{ notice }}</p>
    <p v-if="error" role="alert" class="message-center__error">
      {{ error }} <button :disabled="busy" @click="load()">重新加载</button>
    </p>
    <p v-if="loading && !rows.length">正在读取消息…</p>
    <p v-else-if="!rows.length" class="message-center__empty">
      当前分类还没有消息。你可以继续浏览商品或查看订单。
    </p>
    <div v-else class="message-center__list">
      <article v-for="row in rows" :key="row.id" :class="{ unread: !row.is_read }">
        <div class="message-center__meta">
          <span>{{ notificationTypes[row.type] || '系统' }}</span><time :datetime="row.created_at">{{ new Date(row.created_at).toLocaleString() }}</time>
        </div>
        <h2>
          <span v-if="!row.is_read" class="message-center__dot" aria-label="未读" />{{ row.title }}
        </h2>
        <p>{{ row.body }}</p>
        <button :disabled="busy || loading" @click="open(row)">
          {{ row.is_read ? '查看关联内容' : '查看并标为已读' }}
        </button>
      </article>
    </div>
    <button v-if="hasMore" :disabled="loading || busy" @click="load(true)">
      {{ loading ? '正在加载…' : '加载更早消息' }}
    </button>
  </section>
</template>
