<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getHome } from '@/api/cms'
import { getCategoryTree } from '@/api/catalog'
import ContentBlocks from '@/components/content/ContentBlocks.vue'
import ProductGrid from '@/components/content/ProductGrid.vue'
import './content.css'

const router = useRouter()
const data = ref(null)
const loading = ref(false)
const error = ref('')
const query = ref('')
const categories = ref([])
const hasContent = computed(
  () => data.value && ['banners', 'floors', 'announcements'].some((key) => data.value[key].length),
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getHome(window.innerWidth < 768 ? 'mobile' : 'web')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function loadCategories() {
  try {
    categories.value = await getCategoryTree()
  } catch {
    categories.value = []
  }
}
function search() {
  router.push({ path: '/products', query: query.value ? { q: query.value } : {} })
}
onMounted(() => {
  load()
  loadCategories()
})
</script>

<template>
  <div class="cms-home">
    <section class="cms-home__hero">
      <p class="cms-home__eyebrow">SIQ优选商城</p>
      <h1>认真选好每一件日常用品</h1>
      <p>真实商品、统一交易规则、可查询的订单与消息。当前为演示商城，支付仅为模拟。</p>
      <form class="cms-home__search" @submit.prevent="search">
        <label class="cms-home__search-label" for="home-search">搜索商品</label>
        <input id="home-search" v-model="query" placeholder="搜索商品名称">
        <button>搜索</button>
      </form>
    </section>
    <nav class="home-categories" aria-label="商品分类"><router-link to="/products">全部商品</router-link><router-link v-for="row in categories" :key="row.id" :to="{ path: '/products', query: { category: row.id } }">{{ row.name }}</router-link></nav>
    <p v-if="error" role="alert" class="cms-error">{{ error }} <button @click="load">重新加载</button></p>
    <p v-else-if="loading" class="cms-loading">正在读取首页内容…</p>
    <template v-else-if="data">
      <section v-for="banner in data.banners" :key="banner.id" class="cms-banner">
        <ContentBlocks :blocks="banner.blocks" />
      </section>
      <section v-if="data.announcements.length" class="cms-announcements">
        <h2>商城公告</h2>
        <ul><li v-for="item in data.announcements" :key="item.id"><router-link :to="`/announcements/${item.id}`">{{ item.title }}</router-link></li></ul>
      </section>
      <section v-for="floor in data.floors" :key="floor.id" class="cms-floor">
        <ContentBlocks :blocks="floor.blocks" />
      </section>
      <section v-if="!hasContent" class="cms-fallback">
        <div class="cms-section-heading"><h2>当前可售商品</h2><p>暂无已发布首页内容，仍可直接选购真实商品。</p></div>
        <ProductGrid :products="data.fallback_products" />
        <p v-if="!data.fallback_products.length" class="cms-empty">暂无已发布内容或可售商品，请稍后再来。</p>
      </section>
      <section class="cms-service"><h2>购物服务</h2><p>订单状态、库存和优惠券以服务端实时结果为准；站内消息始终可查，不依赖订阅授权。</p><router-link to="/products">浏览全部商品</router-link></section>
    </template>
  </div>
</template>
