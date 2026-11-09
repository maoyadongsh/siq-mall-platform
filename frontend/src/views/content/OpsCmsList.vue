<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { cmsKinds, createContent, listContents, publicationStates } from '@/api/cms'
import './content.css'

const router = useRouter()
const rows = ref([])
const kind = ref('')
const page = ref(1)
const totalPages = ref(1)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const creating = ref(false)
const form = ref({ kind: 'banner', title: '', slug: '', productIds: '' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listContents({ kind: kind.value || undefined, page: page.value, page_size: 20 })
    rows.value = data.results
    totalPages.value = data.total_pages
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function filter() {
  page.value = 1
  load()
}
async function create() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const blocks = form.value.kind === 'floor'
      ? [{ type: 'product_list', product_ids: form.value.productIds.split(/[，,\s]+/).filter(Boolean).map(Number) }]
      : [{ type: 'text', text: '请在编辑器中完善内容。' }]
    const now = new Date()
    const end = new Date(now.getTime() + 7 * 86400000)
    const result = await createContent({
      kind: form.value.kind,
      slug: form.value.slug,
      title: form.value.title,
      blocks,
      platforms: ['web', 'mobile', 'mini'],
      sort_order: 0,
      start_at: now.toISOString(),
      end_at: end.toISOString(),
    })
    await router.push(`/ops/cms/${result.id}/edit`)
  } catch (e) {
    error.value = e.response?.data?.errors?.[0]?.detail || e.message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="cms-ops">
    <div class="cms-ops__heading"><div><h1>内容管理</h1><p>草稿与线上版本隔离，公开内容仅在发布时段和所选展示端生效。</p></div><button @click="creating = !creating">{{ creating ? '收起' : '新建内容' }}</button></div>
    <form v-if="creating" class="cms-create" @submit.prevent="create">
      <label>类型<select v-model="form.kind"><option v-for="(label, key) in cmsKinds" :key="key" :value="key">{{ label }}</option></select></label>
      <label>标题<input v-model.trim="form.title" maxlength="120" required></label>
      <label>内容标识（单页必填）<input v-model.trim="form.slug" pattern="[a-z0-9][a-z0-9-]*" :required="form.kind === 'page'" placeholder="service-guide"></label>
      <label v-if="form.kind === 'floor'">初始推荐商品ID<input v-model="form.productIds" required placeholder="例如：1,2"></label>
      <button :disabled="busy || !form.title">保存草稿并编辑</button>
    </form>
    <form class="cms-filter" @submit.prevent="filter"><label>内容类型<select v-model="kind"><option value="">全部</option><option v-for="(label, key) in cmsKinds" :key="key" :value="key">{{ label }}</option></select></label><button>筛选</button></form>
    <p v-if="error" role="alert" class="cms-error">{{ error }}</p>
    <p v-if="loading">正在读取内容…</p>
    <p v-else-if="!rows.length" class="cms-empty">当前筛选下没有内容，可新建草稿。</p>
    <div v-else class="cms-table-wrap"><table class="cms-table"><thead><tr><th>标题 / 类型</th><th>发布状态</th><th>线上 / 最新版本</th><th>操作</th></tr></thead><tbody><tr v-for="row in rows" :key="row.id"><td><strong>{{ row.latest_revision.title }}</strong><small>{{ cmsKinds[row.kind] }} · {{ row.slug }}</small></td><td>{{ publicationStates[row.publication_state] }}</td><td>{{ row.published_revision || '—' }} / {{ row.latest_revision.revision_no }}</td><td><router-link :to="`/ops/cms/${row.id}/edit`">编辑与预览</router-link></td></tr></tbody></table></div>
    <nav class="cms-pagination"><button :disabled="page <= 1 || loading" @click="page--; load()">上一页</button><span>{{ page }} / {{ totalPages }}</span><button :disabled="page >= totalPages || loading" @click="page++; load()">下一页</button></nav>
  </section>
</template>
