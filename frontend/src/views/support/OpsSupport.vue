<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { assignConversation, listConversations } from '@/api/support'
import SupportChat from '@/components/support/SupportChat.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const scope = ref('mine')
const rows = ref([])
const selectedId = ref('')
const agentId = ref(userStore.profile.id)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
let timer

async function loadQueue() {
  if (document.visibilityState !== 'visible') return
  loading.value = true
  error.value = ''
  try {
    const data = await listConversations({ scope: scope.value, page_size: 50 }, true)
    rows.value = data.results
    if (!selectedId.value && rows.value.length) selectedId.value = rows.value[0].id
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function assign() {
  const row = rows.value.find((item) => item.id === selectedId.value)
  if (!row || busy.value || !agentId.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await assignConversation(row, agentId.value, '工作台分配')
    scope.value = 'mine'
    await loadQueue()
    notice.value = '会话已分配，可由接待客服回复。'
  } catch (e) {
    error.value = e.response ? e.message : `${e.message}；分配结果待确认，请刷新或重试。`
  } finally {
    busy.value = false
  }
}
function visibility() {
  if (document.visibilityState === 'visible') loadQueue()
}
onMounted(() => {
  loadQueue()
  timer = setInterval(loadQueue, 10000)
  document.addEventListener('visibilitychange', visibility)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', visibility)
})
</script>

<template>
  <div class="ops-support">
    <header><div><h1>客服工作台</h1><p>仅显示权限内会话；分配、未读和已读均来自服务端记录。</p></div><label>队列<select v-model="scope" @change="selectedId = ''; loadQueue()"><option value="mine">我的接待</option><template v-if="userStore.profile.can_assign_support"><option value="pending">待分配</option><option value="closed">已关闭</option><option value="all">全部授权会话</option></template></select></label></header>
    <p v-if="error" role="alert" class="ops-support__error">{{ error }}</p><p v-if="notice" role="status" class="ops-support__success">{{ notice }}</p>
    <div class="ops-support__layout">
      <aside class="ops-support__queue"><h2>会话队列</h2><p v-if="loading">正在刷新…</p><p v-if="!rows.length">当前队列暂无会话。</p><button v-for="row in rows" :key="row.id" :aria-pressed="selectedId === row.id" @click="selectedId = row.id"><strong>#{{ row.id }} · {{ row.status === 'open' ? '进行中' : '已关闭' }}</strong><span>{{ row.buyer_display_name }} · 未读 {{ row.unread_count }}</span><small v-if="row.last_message">{{ row.last_message.body }}</small></button></aside>
      <main class="ops-support__main"><SupportChat v-if="selectedId" :key="selectedId" :conversation-id="selectedId" ops @changed="loadQueue" /><p v-else class="ops-support__empty">请选择需要处理的会话。</p></main>
      <aside class="ops-support__assignment"><h2>分配与权限</h2><template v-if="userStore.profile.can_assign_support"><label>客服用户ID<input v-model="agentId" inputmode="numeric"></label><button :disabled="busy || !selectedId" @click="assign">分配给此客服</button></template><p v-else>你可以处理分配给自己的会话，不能查看或接管其他客服会话。</p><p>客服仅查看必要的订单摘要，不提供收货地址或任意改价、发货入口。</p></aside>
    </div>
  </div>
</template>

<style scoped>
.ops-support__layout {
  display: grid;
  grid-template-columns: minmax(200px, 0.75fr) minmax(360px, 1.8fr) minmax(200px, 0.75fr);
  gap: 16px;
  align-items: start;
}
.ops-support header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.ops-support select,
.ops-support input {
  min-height: 44px;
  padding: 8px;
  border: 1px solid var(--mall-border);
  border-radius: 6px;
  font: inherit;
}
.ops-support__queue,
.ops-support__assignment,
.ops-support__main {
  min-width: 0;
  padding: 14px;
  border-radius: 12px;
  background: #fff;
}
.ops-support__queue {
  display: grid;
  gap: 8px;
}
.ops-support__queue button {
  display: grid;
  gap: 5px;
  min-height: 44px;
  padding: 10px;
  border: 1px solid var(--mall-border);
  border-radius: 8px;
  text-align: left;
  background: #fff;
}
.ops-support__queue button[aria-pressed='true'] {
  border-color: var(--mall-color-primary);
  background: var(--mall-color-primary-light);
}
.ops-support__queue small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ops-support__assignment {
  display: grid;
  gap: 12px;
}
.ops-support__assignment button {
  min-height: 44px;
  color: #fff;
  background: var(--mall-color-primary);
  border: 0;
  border-radius: 8px;
}
.ops-support__error {
  color: #8b2c2c;
}
.ops-support__success {
  color: var(--mall-color-primary);
}
.ops-support__empty {
  text-align: center;
}
@media (max-width: 1050px) {
  .ops-support__layout {
    grid-template-columns: 1fr;
  }
  .ops-support__queue {
    max-height: 320px;
    overflow-y: auto;
  }
}
</style>
