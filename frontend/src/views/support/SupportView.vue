<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createConversation, listConversations } from '@/api/support'
import SupportChat from '@/components/support/SupportChat.vue'

const props = defineProps({ id: { type: String, default: '' } })
const router = useRouter()
const rows = ref([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')

async function load() {
  if (props.id) return
  loading.value = true
  error.value = ''
  try {
    const data = await listConversations({ page_size: 50 })
    rows.value = data.results
    const active = rows.value.find((row) => row.status === 'open')
    if (active) await router.replace(`/support/${active.id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function create() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const row = await createConversation()
    await router.push(`/support/${row.id}`)
  } catch (e) {
    error.value = e.response ? e.message : `${e.message}；请核对是否已创建，不要更换提交标识。`
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="support-page">
    <SupportChat v-if="id" :conversation-id="id" @new-conversation="create" />
    <section v-else>
      <h1>联系客服</h1><p>可以咨询商品、订单和履约问题。会话记录仅本人及授权客服可见，不显示虚构在线状态。</p>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="loading">正在读取会话…</p>
      <button :disabled="busy" @click="create">{{ busy ? '正在核对会话…' : '开始新会话' }}</button>
      <section v-if="rows.length"><h2>历史会话</h2><article v-for="row in rows" :key="row.id"><router-link :to="`/support/${row.id}`">会话 #{{ row.id }} · {{ row.status === 'open' ? '进行中' : '已关闭' }}</router-link><p v-if="row.last_message">{{ row.last_message.body }}</p></article></section>
    </section>
  </div>
</template>

<style scoped>
.support-page {
  max-width: 900px;
  margin: 0 auto;
}
.support-page button {
  min-height: 44px;
  padding: 8px 16px;
  border: 1px solid var(--mall-border);
  border-radius: 8px;
  color: #fff;
  background: var(--mall-color-primary);
}
.support-page article {
  margin: 12px 0;
  padding: 14px;
  background: #fff;
}
.support-page a {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  color: var(--mall-color-primary);
}
</style>
