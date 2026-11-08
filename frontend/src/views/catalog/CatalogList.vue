<script setup>
import { ref, watch } from 'vue'
import request from '@/utils/request'
import DraftForm from './DraftForm.vue'

const props = defineProps({ manage: Boolean })
const query = ref('')
const currentQuery = ref('')
const page = ref(1)
const result = ref({ results: [], total_pages: 0 })
const pending = ref(false)
const actionPending = ref(false)
const error = ref('')
const creating = ref(false)
let generation = 0

async function load() {
  const ticket = ++generation
  pending.value = true
  error.value = ''
  try {
    const data = await request.get(props.manage ? '/ops/products/' : '/products/', {
      params: { q: currentQuery.value, page: page.value },
    })
    if (ticket === generation) result.value = data
  } catch (e) {
    if (ticket === generation) error.value = e.message
  } finally {
    if (ticket === generation) pending.value = false
  }
}
function draftSaved() {
  creating.value = false
  search()
}
function search() {
  page.value = 1
  currentQuery.value = query.value
  load()
}
async function change(product) {
  actionPending.value = true
  const action = product.status === 'on_sale' ? 'unpublish' : 'publish'
  try {
    await request.post('/ops/products/' + product.id + '/' + action + '/', {
      expected_version: product.version,
    })
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    actionPending.value = false
  }
}
function turn(delta) {
  page.value += delta
  load()
}
watch(
  () => props.manage,
  () => {
    creating.value = false
    query.value = ''
    search()
  },
  { immediate: true },
)
</script>
<template>
  <section class="catalog">
    <header>
      <h1>{{ manage ? '商品管理' : '选购商品' }}</h1>
      <button v-if="manage" @click="creating = !creating">
        {{ creating ? '收起' : '新建商品' }}
      </button>
    </header>
    <DraftForm v-if="creating && manage" @saved="draftSaved" />
    <form class="search" @submit.prevent="search">
      <input v-model="query" aria-label="商品名称" placeholder="搜索商品名称"><button>
        搜索
      </button>
    </form>
    <p v-if="error" role="alert">{{ error }} <button @click="load">刷新列表</button></p>
    <p v-else-if="pending">正在加载商品…</p>
    <p v-else-if="!result.results.length">
      {{ currentQuery ? '没有找到相关商品，请调整搜索词。' : '暂无商品。' }}
    </p>
    <div v-else class="cards">
      <article v-for="p in result.results" :key="p.id">
        <img
          v-if="p.cover_url"
          class="product-cover"
          :src="p.cover_url"
          :alt="p.title"
          loading="lazy"
        >
        <small>{{ p.category }}</small>
        <h2>{{ p.title }}</h2>
        <p>¥{{ p.skus.reduce((a, b) => (Number(a.price) <= Number(b.price) ? a : b)).price }} 起</p>
        <template v-if="manage">
          <router-link :to="'/ops/products/' + p.id + '/edit'">维护商品</router-link>
          <span>{{ { draft: '草稿', on_sale: '在售', off_sale: '已下架' }[p.status] }}</span>
          <button :disabled="actionPending" @click="change(p)">
            {{ p.status === 'on_sale' ? '下架' : '上架' }}
          </button>
        </template>
        <router-link v-else :to="'/products/' + p.id">查看规格</router-link>
      </article>
    </div>
    <nav v-if="!error && result.total_pages > 1">
      <button :disabled="pending || page === 1" @click="turn(-1)">上一页</button> {{ page }} /
      {{ result.total_pages }}
      <button :disabled="pending || page >= result.total_pages" @click="turn(1)">下一页</button>
    </nav>
  </section>
</template>
<style src="./catalog.css"></style>
