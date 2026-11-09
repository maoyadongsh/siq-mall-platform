<script setup>
import { onMounted, ref } from 'vue'
import { getAudits } from '@/api/operations'

const data = ref(null)
const objectType = ref('')
const objectId = ref('')
const action = ref('')
const page = ref(1)
const loading = ref(false)
const error = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getAudits({
      page: page.value,
      object_type: objectType.value || undefined,
      object_id: objectId.value || undefined,
      action: action.value || undefined,
    })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function search() {
  page.value = 1
  load()
}
onMounted(load)
</script>

<template>
  <section class="ops-audits">
    <h1>只读运营审计</h1><p>查看现有事实表中的对象、动作、操作者和时间；不提供编辑或删除入口。</p>
    <form class="ops-audits__filters" @submit.prevent="search"><label>对象类型<input v-model="objectType" placeholder="order / content / user_role"></label><label>对象ID<input v-model="objectId"></label><label>动作<input v-model="action" placeholder="publish / update"></label><button>查询</button></form>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="loading">正在读取审计…</p>
    <template v-else-if="data"><p v-if="!data.results.length">当前筛选下没有审计记录。</p><div v-else class="ops-audits__table"><table><thead><tr><th>时间</th><th>操作者</th><th>对象</th><th>动作</th><th>摘要</th></tr></thead><tbody><tr v-for="row in data.results" :key="row.id"><td>{{ new Date(row.created_at).toLocaleString() }}</td><td>{{ row.actor }}</td><td>{{ row.object_type }} / {{ row.object_id }}</td><td>{{ row.action }}</td><td><code>{{ JSON.stringify(row.summary) }}</code></td></tr></tbody></table></div><nav><button :disabled="data.page <= 1" @click="page--; load()">上一页</button><span>{{ data.page }} / {{ data.total_pages }}</span><button :disabled="data.page >= data.total_pages" @click="page++; load()">下一页</button></nav></template>
  </section>
</template>

<style scoped>
.ops-audits__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
  margin: 18px 0;
}
.ops-audits__filters label {
  display: grid;
  gap: 5px;
}
.ops-audits input,
.ops-audits button {
  min-height: 44px;
  padding: 8px 10px;
  font: inherit;
}
.ops-audits__table {
  overflow-x: auto;
}
.ops-audits table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}
.ops-audits th,
.ops-audits td {
  padding: 12px;
  border-bottom: 1px solid var(--mall-border);
  text-align: left;
  vertical-align: top;
}
.ops-audits code {
  overflow-wrap: anywhere;
}
.ops-audits nav {
  display: flex;
  gap: 12px;
  margin: 16px 0;
}
</style>
