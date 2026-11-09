<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchAddresses } from '@/api/addresses'
import { getCart, quote } from '@/api/cart'

import { useUserStore } from '@/stores/user'
const user = useUserStore()
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
    const next = await quote(selected.value, lines)
    if (ticket !== generation) return
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
    result.value = next
    now.value = Date.now()
  } catch (e) {
    if (ticket === generation) error.value = e.message
  } finally {
    if (ticket === generation) loading.value = false
  }
}
onMounted(() => {
  refresh()
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
      <select v-model="selected" @change="refresh">
        <option v-for="a in addresses" :key="a.id" :value="a.id">
          {{ a.recipient }} · {{ a.province }}{{ a.city }}{{ a.district }}{{ a.detail }}
        </option>
      </select></label>
    <p v-if="loading">正在核对价格与库存…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!addresses.length">
      请先添加收货地址。 <router-link to="/account/addresses">管理地址</router-link>
    </p>
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
    <button :disabled="loading" @click="refresh">重新试算</button>
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
