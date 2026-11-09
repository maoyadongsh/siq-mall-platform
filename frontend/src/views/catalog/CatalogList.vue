<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/utils/request'
import { getCategoryTree } from '@/api/catalog'
import DraftForm from './DraftForm.vue'

const props = defineProps({ manage: Boolean })
const route = useRoute()
const router = useRouter()
const query = ref('')
const category = ref('')
const minPrice = ref('')
const maxPrice = ref('')
const sort = ref('newest')
const categories = ref([])
const page = ref(1)
const result = ref({ results: [], total_pages: 0 })
const pending = ref(false)
const actionPending = ref(false)
const error = ref('')
const creating = ref(false)
let generation = 0

async function loadCategories() {
  try {
    const flatten = (rows, output = []) => {
      rows.forEach((row) => {
        output.push(row)
        flatten(row.children || [], output)
      })
      return output
    }
    categories.value = flatten(await getCategoryTree())
  } catch {
    categories.value = []
  }
}
function params() {
  return {
    q: query.value || undefined,
    category: category.value || undefined,
    min_price: minPrice.value || undefined,
    max_price: maxPrice.value || undefined,
    sort: sort.value,
    page: page.value,
  }
}
async function load() {
  const ticket = ++generation
  pending.value = true
  error.value = ''
  try {
    const data = await request.get(props.manage ? '/ops/products/' : '/products/', { params: params() })
    if (ticket === generation) result.value = data
  } catch (e) {
    if (ticket === generation) error.value = e.message
  } finally {
    if (ticket === generation) pending.value = false
  }
}
function search() {
  page.value = 1
  router.push({ path: props.manage ? '/ops/products' : '/products', query: params() })
}
function draftSaved() {
  creating.value = false
  search()
}
function clearFilters() {
  query.value = ''
  category.value = ''
  minPrice.value = ''
  maxPrice.value = ''
  sort.value = 'newest'
  search()
}
async function change(product) {
  actionPending.value = true
  const action = product.status === 'on_sale' ? 'unpublish' : 'publish'
  try {
    await request.post('/ops/products/' + product.id + '/' + action + '/', { expected_version: product.version })
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    actionPending.value = false
  }
}
function turn(delta) {
  page.value += delta
  router.push({ path: route.path, query: params() })
}
watch(
  () => [props.manage, route.query],
  () => {
    creating.value = false
    query.value = props.manage ? '' : String(route.query.q || '')
    category.value = String(route.query.category || '')
    minPrice.value = String(route.query.min_price || '')
    maxPrice.value = String(route.query.max_price || '')
    sort.value = String(route.query.sort || 'newest')
    page.value = Math.max(1, Number(route.query.page || 1))
    load()
  },
  { immediate: true, deep: true },
)
watch(() => props.manage, loadCategories, { immediate: true })
</script>

<template>
  <section class="catalog">
    <header><div><h1>{{ manage ? '商品管理' : '选购商品' }}</h1><router-link v-if="manage" to="/ops/categories">分类管理</router-link></div><button v-if="manage" @click="creating = !creating">{{ creating ? '收起' : '新建商品' }}</button></header>
    <DraftForm v-if="creating && manage" @saved="draftSaved" />
    <form class="search" @submit.prevent="search">
      <input v-model="query" aria-label="商品名称" placeholder="搜索商品名称">
      <select v-model="category" aria-label="分类筛选"><option value="">全部分类</option><option v-for="row in categories" :key="row.id" :value="row.id">{{ row.name }}</option></select>
      <input v-model="minPrice" aria-label="最低价格" inputmode="decimal" placeholder="最低价">
      <input v-model="maxPrice" aria-label="最高价格" inputmode="decimal" placeholder="最高价">
      <select v-model="sort" aria-label="排序方式"><option value="newest">最新</option><option value="price_asc">价格从低到高</option><option value="price_desc">价格从高到低</option><option value="title">名称</option></select>
      <button>查询</button><button type="button" @click="clearFilters">清空筛选</button>
    </form>
    <p v-if="error" role="alert">{{ error }} <button @click="load">刷新列表</button></p>
    <p v-else-if="pending">正在加载商品…</p>
    <p v-else-if="!result.results.length">没有找到相关商品，请调整或清空筛选。</p>
    <div v-else class="cards">
      <article v-for="p in result.results" :key="p.id">
        <img v-if="p.cover_url" class="product-cover" :src="p.cover_url" :alt="p.title" loading="lazy">
        <small>{{ p.category }}</small><h2>{{ p.title }}</h2><p>¥{{ p.skus.reduce((a, b) => (Number(a.price) <= Number(b.price) ? a : b)).price }} 起</p>
        <template v-if="manage"><router-link :to="'/ops/products/' + p.id + '/edit'">维护商品</router-link><span>{{ { draft: '草稿', on_sale: '在售', off_sale: '已下架' }[p.status] }}</span><button :disabled="actionPending" @click="change(p)">{{ p.status === 'on_sale' ? '下架' : '上架' }}</button></template>
        <router-link v-else :to="{ path: '/products/' + p.id, query: { from: 'list' } }">查看规格</router-link>
      </article>
    </div>
    <nav v-if="!error && result.total_pages > 1"><button :disabled="pending || page === 1" @click="turn(-1)">上一页</button> {{ page }} / {{ result.total_pages }}<button :disabled="pending || page >= result.total_pages" @click="turn(1)">下一页</button></nav>
  </section>
</template>
<style src="./catalog.css"></style>
