<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getHome } from '@/api/cms'
import { getCategoryTree } from '@/api/catalog'
import { messageOf } from '@/utils/errors'
import type { Category, Product } from '@/types/models'
import ContentBlocks from '@/components/content/ContentBlocks.vue'
import ProductGrid from '@/components/content/ProductGrid.vue'
import './content.css'

interface HomeSection {
  id: string
  blocks: Record<string, unknown>[]
}

interface HomeAnnouncement {
  id: string
  title: string
}

interface HomeData {
  banners: HomeSection[]
  floors: HomeSection[]
  announcements: HomeAnnouncement[]
  fallback_products: Product[]
}

const router = useRouter()
const data = ref<HomeData | null>(null)
const loading = ref(false)
const error = ref('')
const query = ref('')
const categories = ref<Category[]>([])
const hasContent = computed(() => {
  const home = data.value
  if (!home) return false
  return [home.banners, home.floors, home.announcements].some((rows) => rows.length > 0)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = (await getHome(window.innerWidth < 768 ? 'mobile' : 'web')) as unknown as HomeData
  } catch (e) {
    error.value = messageOf(e)
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
      <div class="cms-home__hero-copy">
        <p class="cms-home__eyebrow">SIQ · CURATED ESSENTIALS</p>
        <h1>把日常，<br>选得更好一点。</h1>
        <p class="cms-home__intro">不追逐繁杂，只认真选好每一件日常用品。价格、库存与订单状态，始终清楚可见。</p>
        <form class="cms-home__search" @submit.prevent="search">
          <label class="siq-sr-only" for="home-search">搜索商品</label>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
          <input id="home-search" v-model="query" placeholder="搜索你需要的日常好物">
          <button>搜索</button>
        </form>
        <ul class="cms-home__assurances" aria-label="购物保障">
          <li>真实商品</li>
          <li>清晰价格</li>
          <li>订单可查</li>
        </ul>
      </div>
      <aside class="cms-home__hero-note">
        <span class="cms-home__note-index">SIQ / 01</span>
        <div>
          <p class="cms-home__note-kicker">GOOD DAILY, GOOD CHOICES</p>
          <h2>好物，<br>不必复杂。</h2>
          <p>从浏览、选择到收货，每一步都有明确反馈。你只需关注真正需要的那一件。</p>
        </div>
        <router-link to="/products">开始选购 <span aria-hidden="true">↗</span></router-link>
      </aside>
    </section>

    <section class="cms-home__category-section" aria-labelledby="category-title">
      <div class="cms-section-heading">
        <div><p class="cms-home__section-kicker">EXPLORE</p><h2 id="category-title">从日常所需开始</h2></div>
        <router-link to="/products">查看全部商品 <span aria-hidden="true">→</span></router-link>
      </div>
      <nav class="home-categories" aria-label="商品分类">
        <router-link to="/products">全部商品</router-link>
        <router-link v-for="row in categories" :key="row.id" :to="{ path: '/products', query: { category: row.id } }">{{ row.name }}</router-link>
      </nav>
    </section>

    <div v-if="error" role="alert" class="cms-error">
      <div><strong>首页内容暂时未能加载</strong><p>{{ error }}</p></div>
      <button @click="load">重新加载</button>
    </div>
    <div v-else-if="loading" class="cms-loading" role="status">
      <span class="cms-loading__line" /><span class="cms-loading__line" /><span class="cms-loading__line" />
      <p>正在为你准备首页内容…</p>
    </div>
    <template v-else-if="data">
      <section v-for="banner in data.banners" :key="banner.id" class="cms-banner">
        <ContentBlocks :blocks="banner.blocks" />
      </section>
      <section v-if="data.announcements.length" class="cms-announcements">
        <div class="cms-section-heading"><div><p class="cms-home__section-kicker">NOTICE</p><h2>商城公告</h2></div></div>
        <ul><li v-for="item in data.announcements" :key="item.id"><router-link :to="`/announcements/${item.id}`"><span>{{ item.title }}</span><span aria-hidden="true">↗</span></router-link></li></ul>
      </section>
      <section v-for="floor in data.floors" :key="floor.id" class="cms-floor">
        <ContentBlocks :blocks="floor.blocks" />
      </section>
      <section v-if="!hasContent" class="cms-fallback">
        <div class="cms-section-heading">
          <div><p class="cms-home__section-kicker">AVAILABLE NOW</p><h2>当前可售商品</h2><p>首页内容尚未发布，仍可直接选购真实商品。</p></div>
        </div>
        <ProductGrid :products="data.fallback_products" />
        <div v-if="!data.fallback_products.length" class="cms-empty">
          <span class="cms-empty__mark" aria-hidden="true">S</span>
          <h2>好物正在准备中</h2>
          <p>暂无已发布内容或可售商品，请稍后再来。</p>
        </div>
      </section>
      <section class="cms-service">
        <div class="cms-service__heading"><p class="cms-home__section-kicker">SHOP WITH CLARITY</p><h2>清楚地选，安心地买。</h2></div>
        <div class="cms-service__grid">
          <div><span>01</span><h3>实时核对</h3><p>订单状态、库存和优惠券以服务端实时结果为准。</p></div>
          <div><span>02</span><h3>消息可查</h3><p>订单与系统消息集中保留，不依赖额外订阅授权。</p></div>
          <div><span>03</span><h3>需要帮助</h3><p>登录后可联系商城客服，继续查询订单与会话记录。</p></div>
        </div>
        <router-link class="cms-service__cta" to="/products">浏览全部商品 <span aria-hidden="true">→</span></router-link>
      </section>
    </template>
  </div>
</template>
