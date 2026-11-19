<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/utils/request'
import { getCategoryTree } from '@/api/catalog'
import { messageOf } from '@/utils/errors'
import type { Product } from '@/types/models'
import ProductGrid from '@/components/content/ProductGrid.vue'
import DraftForm from './DraftForm.vue'

interface CategoryNode {
  id: string
  name: string
  children?: unknown[]
}

type ProductRow = Product & { status: NonNullable<Product['status']> }

interface ProductListState {
  results: ProductRow[]
  total_pages: number
}

const props = defineProps({ manage: Boolean })
const route = useRoute()
const router = useRouter()
const query = ref('')
const category = ref('')
const minPrice = ref('')
const maxPrice = ref('')
const sort = ref('newest')
const categories = ref<CategoryNode[]>([])
const page = ref(1)
const result = ref<ProductListState>({ results: [], total_pages: 0 })
const pending = ref(false)
const actionPending = ref(false)
const error = ref('')
const creating = ref(false)
let generation = 0

async function loadCategories() {
  try {
    const flatten = (rows: CategoryNode[], output: CategoryNode[] = []): CategoryNode[] => {
      rows.forEach((row) => {
        output.push(row)
        flatten((row.children ?? []) as CategoryNode[], output)
      })
      return output
    }
    categories.value = flatten(await getCategoryTree())
  } catch {
    categories.value = []
  }
}
function params(): Record<string, string | number | undefined> {
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
    const data = await request.get<ProductListState>(props.manage ? '/ops/products/' : '/products/', { params: params() })
    if (ticket === generation) result.value = data
  } catch (e) {
    if (ticket === generation) error.value = messageOf(e)
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
function startingPrice(product: ProductRow) {
  return product.skus.reduce((lowest, sku) => Number(sku.price) < Number(lowest.price) ? sku : lowest, product.skus[0]).price
}
async function change(product: ProductRow) {
  actionPending.value = true
  const action = product.status === 'on_sale' ? 'unpublish' : 'publish'
  try {
    await request.post('/ops/products/' + product.id + '/' + action + '/', { expected_version: product.version })
    await load()
  } catch (e) {
    error.value = messageOf(e)
  } finally {
    actionPending.value = false
  }
}
function turn(delta: number) {
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
  <section class="catalog" :class="{ 'catalog--manage': manage }">
    <header class="catalog__header">
      <div>
        <p class="catalog__eyebrow">{{ manage ? 'CATALOG MANAGEMENT' : 'CURATED FOR EVERYDAY' }}</p>
        <h1>{{ manage ? '商品管理' : '找到适合日常的那一件' }}</h1>
        <p class="catalog__subtitle">{{ manage ? '维护商品信息、规格与上架状态。' : '按分类、价格与名称慢慢筛选，不必急着做决定。' }}</p>
      </div>
      <div class="catalog__header-actions">
        <router-link v-if="manage" to="/ops/categories">分类管理</router-link>
        <button v-if="manage" class="catalog-button catalog-button--primary" @click="creating = !creating">{{ creating ? '收起' : '新建商品' }}</button>
      </div>
    </header>
    <DraftForm v-if="creating && manage" @saved="draftSaved" />

    <form class="search catalog__filters" @submit.prevent="search">
      <label class="catalog__filter catalog__filter-query"><span>商品名称</span><input v-model="query" placeholder="搜索商品名称"></label>
      <label class="catalog__filter"><span>分类</span><select v-model="category"><option value="">全部分类</option><option v-for="row in categories" :key="row.id" :value="row.id">{{ row.name }}</option></select></label>
      <div class="catalog__filter catalog__filter--price">
        <span>价格区间</span>
        <div><input v-model="minPrice" aria-label="最低价格" inputmode="decimal" placeholder="最低价"><i aria-hidden="true">—</i><input v-model="maxPrice" aria-label="最高价格" inputmode="decimal" placeholder="最高价"></div>
      </div>
      <label class="catalog__filter"><span>排序</span><select v-model="sort"><option value="newest">最新</option><option value="price_asc">价格从低到高</option><option value="price_desc">价格从高到低</option><option value="title">名称</option></select></label>
      <div class="catalog__filter-actions"><button class="catalog-button catalog-button--primary">查询</button><button class="catalog-button" type="button" @click="clearFilters">清空筛选</button></div>
    </form>

    <div v-if="error" role="alert" class="catalog__state catalog__state--error"><span>{{ error }}</span><button @click="load">刷新列表</button></div>
    <div v-if="pending && !result.results.length" class="catalog__state" role="status">正在加载商品…</div>
    <div v-else-if="!result.results.length && !pending && !error" class="catalog__state">
      <span class="catalog__empty-mark" aria-hidden="true">S</span>
      <h2>没有找到相关商品</h2>
      <p>试试调整关键词或价格区间，也可以从全部商品重新开始。</p>
      <button class="catalog-button" @click="clearFilters">清空筛选</button>
    </div>
    <template v-else-if="result.results.length">
      <ProductGrid v-if="!manage" :products="result.results" />
      <div v-else class="catalog__table-wrap">
        <table class="catalog__table">
          <thead><tr><th>商品</th><th>分类</th><th>起售价</th><th>状态</th><th>版本</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="p in result.results" :key="p.id">
              <td><div class="catalog__product-cell"><img v-if="p.cover_url" :src="p.cover_url" alt="" loading="lazy"><div><strong>{{ p.title }}</strong><small>{{ p.skus.length }} 个规格</small></div></div></td>
              <td>{{ p.category }}</td>
              <td class="siq-price">¥{{ startingPrice(p) }}</td>
              <td><span class="catalog-status" :class="`catalog-status--${p.status}`">{{ { draft: '草稿', on_sale: '在售', off_sale: '已下架' }[p.status] }}</span></td>
              <td>v{{ p.version }}</td>
              <td><div class="catalog__row-actions"><router-link :to="'/ops/products/' + p.id + '/edit'">维护商品</router-link><button :disabled="actionPending" @click="change(p)">{{ p.status === 'on_sale' ? '下架' : '上架' }}</button></div></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <nav v-if="result.total_pages > 1" class="catalog__pagination" aria-label="商品分页">
      <button class="catalog-button" :disabled="pending || page === 1" @click="turn(-1)">上一页</button>
      <span><strong>{{ page }}</strong> / {{ result.total_pages }}</span>
      <button class="catalog-button" :disabled="pending || page >= result.total_pages" @click="turn(1)">下一页</button>
    </nav>
  </section>
</template>
<style src="./catalog.css"></style>
