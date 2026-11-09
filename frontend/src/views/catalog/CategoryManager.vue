<script setup>
import { computed, onMounted, ref } from 'vue'
import { getCategoryTree, saveCategory } from '@/api/catalog'

const rows = ref([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const editing = ref(null)
const form = ref({ name: '', parent_id: null, sort_order: 0, enabled: true })
const flat = computed(() => {
  const output = []
  const walk = (nodes, depth) => nodes.forEach((row) => {
    output.push({ ...row, depth })
    walk(row.children || [], depth + 1)
  })
  walk(rows.value, 0)
  return output
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await getCategoryTree(true)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function edit(row) {
  editing.value = row
  form.value = {
    name: row.name,
    parent_id: row.parent_id,
    sort_order: row.sort_order,
    enabled: row.enabled,
  }
  notice.value = ''
}
async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await saveCategory(form.value, editing.value)
    editing.value = null
    form.value = { name: '', parent_id: null, sort_order: 0, enabled: true }
    notice.value = '分类已保存，公开树会按启停与父子关系更新。'
    await load()
  } catch (e) {
    error.value = e.response?.data?.errors?.[0]?.detail || e.message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="catalog">
    <header><div><h1>分类管理</h1><p>分类不能成环；停用父分类后，其子树不在公开导航返回。</p></div><router-link to="/ops/products">返回商品管理</router-link></header>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
    <form class="draft" @submit.prevent="save">
      <h2>{{ editing ? '编辑分类' : '新建分类' }}</h2>
      <label>分类名称<input v-model.trim="form.name" maxlength="50" required></label>
      <label>父分类<select v-model="form.parent_id"><option :value="null">根分类</option><option v-for="row in flat.filter((item) => item.id !== editing?.id)" :key="row.id" :value="Number(row.id)">{{ '　'.repeat(row.depth) + row.name }}</option></select></label>
      <label>排序<input v-model.number="form.sort_order" type="number"></label>
      <label><input v-model="form.enabled" type="checkbox"> 在公开导航启用</label>
      <button :disabled="busy || !form.name">{{ editing ? '保存修改' : '创建分类' }}</button><button v-if="editing" type="button" @click="editing = null; form = { name: '', parent_id: null, sort_order: 0, enabled: true }">取消编辑</button>
    </form>
    <p v-if="loading">正在读取分类…</p><p v-else-if="!flat.length">暂无分类。</p>
    <table v-else><thead><tr><th>名称</th><th>状态</th><th>排序</th><th>版本</th><th>操作</th></tr></thead><tbody><tr v-for="row in flat" :key="row.id"><td :style="{ paddingLeft: `${row.depth * 24 + 12}px` }">{{ row.name }}</td><td>{{ row.enabled ? '启用' : '停用' }}</td><td>{{ row.sort_order }}</td><td>{{ row.version }}</td><td><button @click="edit(row)">编辑</button></td></tr></tbody></table>
  </section>
</template>
<style src="./catalog.css"></style>
