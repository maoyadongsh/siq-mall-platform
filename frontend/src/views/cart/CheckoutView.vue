<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchAddresses } from '@/api/addresses'
import { getCart, quote } from '@/api/cart'

import { useUserStore } from '@/stores/user'
import { useRouter, useRoute } from 'vue-router'
import { pendingCommand, submitCommand } from '@/api/orders'
const route = useRoute()
const coupon = ref(typeof route.query.coupon === 'string' ? route.query.coupon : ''),
  options = ref([]),
  unavailable = ref([])
const router = useRouter()
const user = useUserStore()
const submitting = ref(false)
const recovery = ref(pendingCommand('order.create', 'checkout'))
async function place() {
  if (submitting.value || (!recovery.value && (!result.value || expired.value))) return
  submitting.value = true
  error.value = ''
  try {
    const data = recovery.value?.data || {
      intent_id: crypto.randomUUID(),
      quote_id: result.value.quote_id,
    }
    const order = await submitCommand('order.create', 'checkout', '/orders/', data)
    await router.push('/orders/' + order.order_no)
  } catch (e) {
    recovery.value = pendingCommand('order.create', 'checkout')
    if (!recovery.value) result.value = null
    error.value = e.message
  } finally {
    submitting.value = false
  }
}
const addresses = ref([]),
  selected = ref(''),
  result = ref(null),
  error = ref(''),
  loading = ref(false),
  changes = ref([]),
  now = ref(Date.now())
let generation = 0,
  timer
const expired = computed(() => result.value && Date.parse(result.value.expires_at) <= now.value)
async function refresh() {
  const ticket = ++generation
  const previous = result.value
  result.value = null
  error.value = ''
  changes.value = []
  loading.value = true
  try {
    const [cart, rows] = await Promise.all([getCart(), fetchAddresses()])
    if (ticket !== generation) return
    addresses.value = rows
    if (!rows.length) return
    if (!rows.some((a) => a.id === selected.value))
      selected.value = (rows.find((a) => a.is_default) || rows[0]).id
    const lines = cart.items.filter((i) => i.selected)
    if (!lines.length) throw new Error('请先在购物车选中商品')
    let next
    try {
      next = await quote(selected.value, lines, coupon.value || null)
    } catch (e) {
      if (coupon.value && [404, 409].includes(e.response?.status) && ticket === generation) {
        const preview = await quote(selected.value, lines)
        if (ticket === generation) {
          options.value = preview.available_coupons
          unavailable.value = preview.unavailable_coupons
        }
      }
      throw e
    }
    if (ticket !== generation) return
    options.value = next.available_coupons
    unavailable.value = next.unavailable_coupons
    const displayed = new Map(
      (previous?.items || lines).map((i) => [i.sku_id, i.unit_price || i.current_price]),
    )
    if (!previous) {
      const stored = sessionStorage.getItem('siq.quote.prices.' + user.profile.id)
      if (stored)
        for (const [id, amount] of Object.entries(JSON.parse(stored))) displayed.set(id, amount)
    }
    changes.value = next.items
      .filter((i) => displayed.has(i.sku_id) && displayed.get(i.sku_id) !== i.unit_price)
      .map((i) => i.title + '：¥' + displayed.get(i.sku_id) + ' → ¥' + i.unit_price)
    if (previous && previous.payable_amount !== next.payable_amount) {
      changes.value.push('预计应付：¥' + previous.payable_amount + ' → ¥' + next.payable_amount)
    }
    result.value = next
    now.value = Date.now()
  } catch (e) {
    if (ticket === generation) error.value = e.message
  } finally {
    if (ticket === generation) loading.value = false
  }
}
onMounted(() => {
  if (!recovery.value) refresh()
  timer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
})
onUnmounted(() => {
  generation++
  clearInterval(timer)
})
</script>
<template>
  <section class="catalog">
    <router-link to="/cart">返回购物车</router-link>
    <h1>结算预览</h1>
    <label v-if="addresses.length">收货地址
      <select v-model="selected" :disabled="submitting || !!recovery" @change="refresh">
        <option v-for="a in addresses" :key="a.id" :value="a.id">
          {{ a.recipient }} · {{ a.province }}{{ a.city }}{{ a.district }}{{ a.detail }}
        </option>
      </select></label>
    <p v-if="loading">正在核对价格与库存…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!recovery && !addresses.length">
      请先添加收货地址。 <router-link to="/account/addresses">管理地址</router-link>
    </p>
    <section v-if="addresses.length && !recovery">
      <label>结算优惠券
        <select v-model="coupon" :disabled="loading || submitting" @change="refresh">
          <option value="">不使用优惠券</option>
          <option v-for="c in options" :key="c.id" :value="c.id">
            {{ c.name }} · 可减 ¥{{ c.discount_amount }}
          </option>
          <option v-if="coupon && !options.some((c) => c.id === coupon)" :value="coupon">
            {{ result?.selected_coupon?.name || '已选优惠券（请核对适用条件）' }}
          </option>
        </select></label>
      <p v-if="!loading && !options.length && !result?.selected_coupon">{{ unavailable.length >= 100 ? '当前展示的券均不适用。' : '当前商品没有可选优惠券。' }}</p>
      <p v-if="options.length + unavailable.length >= 100">此处优先展示最早到期的100张券。<router-link to="/account/coupons">打开完整券包</router-link></p>
      <details v-if="unavailable.length">
        <summary>查看不可用原因</summary>
        <ul>
          <li v-for="c in unavailable" :key="c.id">{{ c.name }}：{{ c.reason }}</li>
        </ul>
      </details>
    </section>
    <article v-if="result">
      <h2>商品明细</h2>
      <p v-for="change in changes" :key="change" role="status">价格已更新：{{ change }}</p>
      <p v-for="i in result.items" :key="i.sku_id">
        {{ i.title }} · {{ i.label }}　¥{{ i.unit_price }} × {{ i.quantity }}　¥{{ i.line_amount }}
      </p>
      <dl>
        <dt>商品合计</dt>
        <dd>¥{{ result.goods_amount }}</dd>
        <dt>配送费</dt>
        <dd>¥{{ result.freight_amount }}</dd>
        <template v-if="result.selected_coupon">
          <dt>优惠 · {{ result.selected_coupon.name }}</dt>
          <dd>−¥{{ result.discount_amount }}</dd>
        </template>
        <dt>预计应付</dt>
        <dd>¥{{ result.payable_amount }}</dd>
      </dl>
      <p>
        {{
          expired
            ? '报价已过期，请重新试算'
            : '报价有效至 ' + new Date(result.expires_at).toLocaleTimeString()
        }}
      </p>
    </article>
    <button v-if="recovery" :disabled="submitting" @click="place">找回上次提交的订单</button>
    <button v-else-if="result" :disabled="expired || loading || submitting" @click="place">
      确认金额并提交订单
    </button>
    <button v-if="!recovery" :disabled="loading || submitting" @click="refresh">重新试算</button>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
select {
  width: 100%;
  max-width: 600px;
  min-height: 44px;
  font: inherit;
}
dl {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}
dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}
</style>
