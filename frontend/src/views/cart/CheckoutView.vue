<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchAddresses } from '@/api/addresses'
import { getCart, quote } from '@/api/cart'

import { useUserStore } from '@/stores/user'
import { useRouter, useRoute } from 'vue-router'
import { pendingCommand, submitCommand } from '@/api/orders'
import type { Address, QuoteData } from '@/types/models'
import { messageOf, statusOf } from '@/utils/errors'

type CheckoutCoupon = {
  id: string
  name: string
  discount_amount: string
  reason?: string
}

type CheckoutQuote = Omit<
  QuoteData,
  'selected_coupon' | 'available_coupons' | 'unavailable_coupons'
> & {
  selected_coupon: CheckoutCoupon | null
  available_coupons: CheckoutCoupon[]
  unavailable_coupons: CheckoutCoupon[]
}

interface CreatedOrder {
  order_no: string
}

const route = useRoute()
const coupon = ref(typeof route.query.coupon === 'string' ? route.query.coupon : ''),
  options = ref<CheckoutCoupon[]>([]),
  unavailable = ref<CheckoutCoupon[]>([])
const router = useRouter()
const user = useUserStore()
const submitting = ref(false)
const recovery = ref(pendingCommand('order.create', 'checkout'))
async function place() {
  if (submitting.value) return
  const current = result.value
  const recoveryOp = recovery.value
  if (!recoveryOp && (!current || expired.value)) return
  submitting.value = true
  error.value = ''
  try {
    const data = recoveryOp?.data || {
      intent_id: crypto.randomUUID(),
      quote_id: current ? current.quote_id : '',
    }
    const order = await submitCommand<CreatedOrder>('order.create', 'checkout', '/orders/', data)
    await router.push('/orders/' + order.order_no)
  } catch (e) {
    recovery.value = pendingCommand('order.create', 'checkout')
    if (!recovery.value) result.value = null
    error.value = messageOf(e)
  } finally {
    submitting.value = false
  }
}
const addresses = ref<Address[]>([]),
  selected = ref(''),
  result = ref<CheckoutQuote | null>(null),
  error = ref(''),
  loading = ref(false),
  changes = ref<string[]>([]),
  now = ref(Date.now())
let generation = 0,
  timer: ReturnType<typeof setInterval> | undefined
const expired = computed(() =>
  result.value ? Date.parse(result.value.expires_at) <= now.value : false,
)
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
    let next: QuoteData
    try {
      next = await quote(selected.value, lines, coupon.value || null)
    } catch (e) {
      if (coupon.value && [404, 409].includes(statusOf(e) ?? 0) && ticket === generation) {
        const preview = await quote(selected.value, lines)
        if (ticket === generation) {
          options.value = preview.available_coupons as CheckoutCoupon[]
          unavailable.value = preview.unavailable_coupons as CheckoutCoupon[]
        }
      }
      throw e
    }
    if (ticket !== generation) return
    options.value = next.available_coupons as CheckoutCoupon[]
    unavailable.value = next.unavailable_coupons as CheckoutCoupon[]
    const displayed = new Map<string, string>(
      (previous?.items || lines).map((i): [string, string] => {
        const price = 'current_price' in i ? i.current_price : i.unit_price
        return [i.sku_id, price]
      }),
    )
    if (!previous) {
      const userId = user.profile?.id
      const stored = userId ? sessionStorage.getItem('siq.quote.prices.' + userId) : null
      if (stored)
        for (const [id, amount] of Object.entries(JSON.parse(stored) as Record<string, string>))
          displayed.set(id, amount)
    }
    changes.value = next.items
      .filter((i) => displayed.has(i.sku_id) && displayed.get(i.sku_id) !== i.unit_price)
      .map((i) => i.title + '：¥' + displayed.get(i.sku_id) + ' → ¥' + i.unit_price)
    if (previous && previous.payable_amount !== next.payable_amount) {
      changes.value.push('预计应付：¥' + previous.payable_amount + ' → ¥' + next.payable_amount)
    }
    result.value = next as CheckoutQuote
    now.value = Date.now()
  } catch (e) {
    if (ticket === generation) error.value = messageOf(e)
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
  <section class="catalog checkout">
    <router-link class="checkout__back" to="/cart"><span aria-hidden="true">←</span> 返回购物车</router-link>
    <header class="checkout__header"><div><p class="catalog__eyebrow">SECURE CHECKOUT</p><h1>结算预览</h1><p>核对收货信息与实时报价，再确认提交订单。</p></div><span><i>1</i> 核对信息 <b /> <i>2</i> 提交订单</span></header>

    <div v-if="loading" class="catalog__state" role="status"><span class="catalog__spinner" aria-hidden="true" />正在核对价格与库存…</div>
    <div v-else-if="error" class="checkout__notice" role="alert"><div><strong>暂时无法完成结算</strong><p>{{ error }}</p></div><button v-if="!recovery" class="catalog-button catalog-button--secondary" :disabled="loading || submitting" @click="refresh">重新试算</button></div>
    <div v-else-if="!recovery && !addresses.length" class="checkout__empty"><span aria-hidden="true">S</span><h2>先添加一个收货地址</h2><p>地址保存后，即可继续核对配送与应付金额。</p><router-link class="catalog-button catalog-button--primary" to="/account/addresses">管理收货地址</router-link></div>

    <div v-if="recovery" class="checkout__recovery" role="status"><div><p class="catalog__eyebrow">SUBMISSION RECOVERY</p><h2>上次提交结果待确认</h2><p>优先找回原订单，避免重复创建。</p></div><button class="catalog-button catalog-button--primary" :disabled="submitting" @click="place">{{ submitting ? '正在核对…' : '找回上次提交的订单' }}</button></div>

    <div v-if="addresses.length && !recovery && !loading && !error" class="checkout__layout">
      <div class="checkout__main">
        <section class="checkout__card">
          <header><span>01</span><div><h2>收货地址</h2><p>选择本次订单的收货信息</p></div><router-link to="/account/addresses">管理地址</router-link></header>
          <label class="checkout__field"><span>配送至</span><select v-model="selected" :disabled="submitting || !!recovery" @change="refresh"><option v-for="a in addresses" :key="a.id" :value="a.id">{{ a.recipient }} · {{ a.province }}{{ a.city }}{{ a.district }}{{ a.detail }}</option></select></label>
        </section>

        <section class="checkout__card">
          <header><span>02</span><div><h2>优惠券</h2><p>仅展示当前商品适用的优惠</p></div></header>
          <label class="checkout__field"><span>结算优惠券</span><select v-model="coupon" :disabled="loading || submitting" @change="refresh"><option value="">不使用优惠券</option><option v-for="c in options" :key="c.id" :value="c.id">{{ c.name }} · 可减 ¥{{ c.discount_amount }}</option><option v-if="coupon && !options.some((c) => c.id === coupon)" :value="coupon">{{ result?.selected_coupon?.name || '已选优惠券（请核对适用条件）' }}</option></select></label>
          <p v-if="!loading && !options.length && !result?.selected_coupon" class="checkout__muted">{{ unavailable.length >= 100 ? '当前展示的券均不适用。' : '当前商品没有可选优惠券。' }}</p>
          <p v-if="options.length + unavailable.length >= 100" class="checkout__muted">此处优先展示最早到期的100张券。<router-link to="/account/coupons">打开完整券包</router-link></p>
          <details v-if="unavailable.length" class="checkout__unavailable"><summary>查看不可用原因（{{ unavailable.length }}）</summary><ul><li v-for="c in unavailable" :key="c.id"><strong>{{ c.name }}</strong><span>{{ c.reason }}</span></li></ul></details>
        </section>

        <article v-if="result" class="checkout__card checkout__items">
          <header><span>03</span><div><h2>商品明细</h2><p>{{ result.items.length }} 种规格，提交前再次核对</p></div></header>
          <div v-if="changes.length" class="checkout__changes" role="status"><strong>报价已更新，请重新确认</strong><p v-for="change in changes" :key="change">{{ change }}</p></div>
          <ul><li v-for="i in result.items" :key="i.sku_id"><div><strong>{{ i.title }}</strong><span>{{ i.label }} · ¥{{ i.unit_price }} × {{ i.quantity }}</span></div><strong class="siq-price">¥{{ i.line_amount }}</strong></li></ul>
        </article>
      </div>

      <aside v-if="result" class="checkout__summary">
        <p class="catalog__eyebrow">PRICE SUMMARY</p><h2>金额明细</h2>
        <dl><div><dt>商品合计</dt><dd>¥{{ result.goods_amount }}</dd></div><div><dt>配送费</dt><dd>¥{{ result.freight_amount }}</dd></div><div v-if="result.selected_coupon"><dt>优惠 · {{ result.selected_coupon.name }}</dt><dd class="checkout__discount">−¥{{ result.discount_amount }}</dd></div><div class="checkout__total"><dt>预计应付</dt><dd><small>¥</small>{{ result.payable_amount }}</dd></div></dl>
        <p class="checkout__expiry" :class="{ 'is-expired': expired }">{{ expired ? '报价已过期，请重新试算' : '报价有效至 ' + new Date(result.expires_at).toLocaleTimeString() }}</p>
        <p class="checkout__summary-note">提交订单即表示已核对本次商品价格、优惠与配送信息。</p>
        <div class="checkout__actions"><div><small>预计应付</small><strong class="siq-price">¥{{ result.payable_amount }}</strong></div><button class="catalog-button catalog-button--primary" :disabled="expired || loading || submitting" @click="place">{{ submitting ? '正在提交…' : '确认金额并提交订单' }}</button><button class="catalog-button catalog-button--text" :disabled="loading || submitting" @click="refresh">重新试算</button></div>
      </aside>
    </div>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
.checkout__back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  margin-bottom: 16px;
  color: var(--mall-text-secondary);
  font-size: 13px;
  text-decoration: none;
}
.checkout__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 32px;
}
.checkout__header h1 {
  margin: 8px 0 10px;
  font-size: clamp(30px, 4vw, 40px);
  font-weight: 600;
}
.checkout__header p:last-child {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 14px;
}
.checkout__header > span {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 5px;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.checkout__header i {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: var(--mall-color-primary);
  font-style: normal;
}
.checkout__header b {
  width: 28px;
  height: 1px;
  margin: 0 3px;
  background: var(--mall-border-strong);
}
.checkout__notice,
.checkout__recovery {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 24px;
  border: 1px solid rgb(180 35 24 / 18%);
  border-radius: var(--mall-radius-lg);
  background: #fff7f5;
}
.checkout__notice strong,
.checkout__notice p {
  color: var(--mall-color-danger);
}
.checkout__notice p,
.checkout__recovery p {
  margin: 4px 0 0;
}
.checkout__recovery {
  border-color: rgb(138 90 24 / 20%);
  background: #fbf5e9;
}
.checkout__recovery h2 {
  margin: 6px 0;
  font-size: 22px;
}
.checkout__empty {
  padding: 64px 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: var(--mall-surface);
  text-align: center;
}
.checkout__empty > span {
  display: grid;
  width: 46px;
  height: 46px;
  margin: 0 auto 18px;
  place-items: center;
  border-radius: 14px 14px 14px 4px;
  color: #fff;
  background: var(--mall-color-primary);
  font-size: 20px;
}
.checkout__empty h2 {
  margin-bottom: 10px;
}
.checkout__empty p {
  margin-bottom: 24px;
  color: var(--mall-text-secondary);
}
.checkout__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 330px;
  gap: 24px;
  align-items: start;
}
.checkout__main {
  display: grid;
  gap: 18px;
  min-width: 0;
}
.checkout__card {
  padding: 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: var(--mall-surface);
}
.checkout__card > header {
  display: flex;
  align-items: center;
  gap: 13px;
  margin-bottom: 20px;
}
.checkout__card > header > span {
  display: grid;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  place-items: center;
  border-radius: 50%;
  color: var(--mall-color-primary);
  background: var(--mall-color-primary-light);
  font-size: 10px;
  font-weight: 650;
}
.checkout__card > header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.checkout__card > header p {
  margin: 3px 0 0;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.checkout__card > header > a {
  margin-left: auto;
  font-size: 12px;
}
.checkout__field {
  display: grid;
  gap: 7px;
}
.checkout__field > span {
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.checkout__field select {
  width: 100%;
  min-height: 48px;
  text-overflow: ellipsis;
}
.checkout__muted {
  margin: 12px 0 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.checkout__unavailable {
  margin-top: 14px;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.checkout__unavailable summary {
  min-height: 44px;
  padding: 11px 0;
  color: var(--mall-color-primary);
  cursor: pointer;
}
.checkout__unavailable ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.checkout__unavailable li {
  display: grid;
  gap: 3px;
  padding: 10px 0;
  border-top: 1px solid var(--mall-border);
}
.checkout__unavailable li strong {
  color: var(--mall-text);
  font-weight: 550;
}
.checkout__changes {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: var(--mall-radius-sm);
  color: var(--mall-color-warning);
  background: #fbf5e9;
  font-size: 12px;
}
.checkout__changes p {
  margin: 5px 0 0;
}
.checkout__items ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.checkout__items li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 0;
  border-top: 1px solid var(--mall-border);
}
.checkout__items li > div {
  min-width: 0;
}
.checkout__items li strong,
.checkout__items li span {
  display: block;
}
.checkout__items li > div > strong {
  overflow-wrap: anywhere;
  font-size: 14px;
  font-weight: 550;
}
.checkout__items li span {
  margin-top: 4px;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.checkout__items li > strong {
  flex-shrink: 0;
  color: var(--mall-color-primary);
  font-size: 14px;
}
.checkout__summary {
  position: sticky;
  top: calc(var(--mall-header-height) + 24px);
  padding: 26px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: var(--mall-surface);
  box-shadow: var(--mall-shadow-sm);
}
.checkout__summary > h2 {
  margin: 7px 0 22px;
  font-size: 22px;
}
.checkout__summary dl {
  margin: 0;
}
.checkout__summary dl > div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.checkout__summary dd {
  margin: 0;
  color: var(--mall-text);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.checkout__summary .checkout__discount {
  color: var(--mall-color-success);
}
.checkout__summary .checkout__total {
  align-items: flex-end;
  margin-top: 10px;
  padding: 18px 0;
  border-top: 1px solid var(--mall-border);
  color: var(--mall-text);
  font-weight: 600;
}
.checkout__total dd {
  color: var(--mall-color-primary);
  font-size: 28px;
  font-weight: 650;
  letter-spacing: -0.035em;
}
.checkout__total dd small {
  margin-right: 3px;
  font-size: 15px;
}
.checkout__expiry {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.checkout__expiry.is-expired {
  color: var(--mall-color-danger);
}
.checkout__summary-note {
  margin: 16px 0;
  color: var(--mall-text-secondary);
  font-size: 10px;
  line-height: 1.7;
}
.checkout__actions {
  display: grid;
  gap: 8px;
}
.checkout__actions > div {
  display: none;
}
.checkout__actions .catalog-button--primary {
  min-height: 50px;
}
@media (max-width: 1000px) {
  .checkout__layout {
    grid-template-columns: 1fr;
  }
  .checkout__summary {
    position: static;
  }
}
@media (max-width: 767px) {
  .checkout {
    padding-bottom: 104px;
  }
  .checkout__header > span {
    display: none;
  }
  .checkout__card,
  .checkout__summary {
    padding: 20px;
  }
  .checkout__notice,
  .checkout__recovery {
    align-items: flex-start;
    flex-direction: column;
  }
  .checkout__actions {
    position: fixed;
    z-index: var(--mall-z-navigation);
    right: 0;
    bottom: 0;
    left: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px max(16px, env(safe-area-inset-right, 0px)) max(10px, env(safe-area-inset-bottom, 0px)) max(16px, env(safe-area-inset-left, 0px));
    border-top: 1px solid var(--mall-border);
    background: rgb(255 255 255 / 95%);
    box-shadow: 0 -8px 24px rgb(24 45 38 / 6%);
    backdrop-filter: blur(16px);
  }
  .checkout__actions > div {
    display: grid;
    flex-shrink: 0;
  }
  .checkout__actions > div small {
    color: var(--mall-text-secondary);
    font-size: 9px;
  }
  .checkout__actions > div strong {
    color: var(--mall-color-primary);
    font-size: 18px;
  }
  .checkout__actions .catalog-button--primary {
    flex: 1;
  }
  .checkout__actions .catalog-button--text {
    display: none;
  }
}
</style>
