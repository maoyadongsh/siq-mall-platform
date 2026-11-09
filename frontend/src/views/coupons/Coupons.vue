<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'
import { offer, stateName, couponAction } from '@/api/coupons'
const props = defineProps({ wallet: Boolean })
const user = useUserStore(),
  router = useRouter()
const data = ref(null),
  page = ref(1),
  filter = ref(''),
  loading = ref(false),
  busy = ref(false),
  error = ref(''),
  notice = ref('')
let generation = 0
async function load(n = 1) {
  const seq = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await request.get(props.wallet ? '/users/me/coupons/' : '/coupons/', {
      params: { page: n, status: filter.value || undefined },
    })
    if (seq === generation) {
      data.value = result
      page.value = n
    }
  } catch (e) {
    if (seq === generation) error.value = e.message
  } finally {
    if (seq === generation) loading.value = false
  }
}
async function claim(c) {
  await user.restoreSession()
  if (!user.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: '/coupons' } })
    return
  }
  if (busy.value) return
  busy.value = true
  notice.value = ''
  error.value = ''
  try {
    await couponAction(c.id, 'claim')
    notice.value = '已领取「' + c.name + '」，可在我的优惠券查看'
    await load(1)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
watch(
  () => props.wallet,
  () => {
    filter.value = ''
    notice.value = ''
    load()
  },
  { immediate: true },
)
</script>
<template>
  <section class="catalog">
    <h1>{{ wallet ? '我的优惠券' : '领券中心' }}</h1>
    <nav>
      <router-link to="/coupons">领券中心</router-link><router-link to="/account/coupons">我的优惠券</router-link>
    </nav>
    <label v-if="wallet">券状态
      <select v-model="filter" @change="load()">
        <option value="">全部</option>
        <option v-for="s in ['unused', 'reserved', 'used', 'expired']" :key="s" :value="s">
          {{ stateName[s] }}
        </option>
      </select></label>
    <p v-if="error" role="alert">{{ error }} <button @click="load()">刷新</button></p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="loading">正在读取优惠券…</p>
    <template v-else-if="data">
      <p v-if="!data.results.length">当前没有符合条件的优惠券。</p>
      <div class="cards">
        <article v-for="c in data.results" :key="c.id">
          <small>{{ c.scope === 'all' ? '全场商品' : '指定商品' }} · {{ stateName[c.status] }}</small>
          <h2>{{ c.name }}</h2>
          <p>{{ offer(c) }}</p>
          <p>使用期限至 {{ new Date(c.end_at).toLocaleString() }}</p>
          <template v-if="!wallet">
            <p>剩余 {{ c.total - c.issued }} 张 · 每人限领 {{ c.per_user_limit }} 张</p>
            <button :disabled="busy" @click="claim(c)">领取优惠券</button>
          </template>
          <router-link
            v-else-if="c.status === 'unused'"
            :to="{ path: '/checkout', query: { coupon: c.id } }"
          >
            去结算使用
          </router-link>
          <router-link v-if="wallet && c.order_no" :to="'/orders/' + c.order_no">
            查看关联订单
          </router-link>
        </article>
      </div>
      <nav v-if="data.total_pages > 1">
        <button :disabled="page === 1" @click="load(page - 1)">上一页</button>{{ page }} /
        {{ data.total_pages
        }}<button :disabled="page === data.total_pages" @click="load(page + 1)">下一页</button>
      </nav>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
