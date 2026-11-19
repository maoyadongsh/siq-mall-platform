<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getOrder, pendingCommand, statusNames, submitCommand } from '@/api/orders'
import type { OrderDetail } from '@/types/models'
import { messageOf } from '@/utils/errors'

type OrderItem = {
  sku_id: string
  title: string
  label: string
  unit_price: string
  quantity: number
}

type OrderAddress = {
  recipient: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
}

type OrderShipment = {
  carrier: string
  tracking_no: string
}

type OrderCoupon = {
  name: string
}

type OrderEvent = {
  type: string
  at: string
  reason?: string
}

type OrderView = Omit<
  OrderDetail,
  'items' | 'address_snapshot' | 'events' | 'shipment' | 'coupon_snapshot'
> & {
  items: OrderItem[]
  address_snapshot: OrderAddress
  events: OrderEvent[]
  shipment: OrderShipment | null
  coupon_snapshot: OrderCoupon | null
}

interface PendingAction {
  key: string
  path: string
  data: Record<string, unknown>
  action: string
}

const props = defineProps({ no: { type: String, required: true }, ops: Boolean })
const order = ref<OrderView | null>(null),
  error = ref(''),
  busy = ref(false),
  loading = ref(false),
  carrier = ref(''),
  tracking = ref(''),
  confirm = ref(''),
  now = ref(Date.now())
const unresolved = ref<PendingAction | null>(null)
function checkPending() {
  unresolved.value = null
  const actions = props.ops
    ? ['order.ship']
    : ['order.cancel', 'order.receive', 'payment.create', 'payment.simulate']
  for (const action of actions) {
    const op = pendingCommand(action, props.no)
    if (op) {
      unresolved.value = { ...op, action }
      break
    }
  }
}
let timer: ReturnType<typeof setInterval> | undefined
const events: Record<string, string> = {
  'order.created': '订单已创建',
  'order.paid': '模拟付款成功',
  'order.shipped': '订单已发货',
  'order.completed': '买家已收货',
  'order.canceled': '订单已取消',
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    order.value = (await getOrder(props.no, props.ops)) as OrderView
    checkPending()
  } catch (e) {
    error.value = messageOf(e)
  } finally {
    loading.value = false
  }
}
async function command(action: string, path: string, data: Record<string, unknown>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await submitCommand(action, props.no, path, data)
    confirm.value = ''
    await load()
  } catch (e) {
    checkPending()
    await load()
    error.value = messageOf(e)
  } finally {
    busy.value = false
  }
}
function cancel() {
  return command('order.cancel', '/orders/' + props.no + '/cancel/', {
    reason: 'user_changed_mind',
  })
}
function receive() {
  return command('order.receive', '/orders/' + props.no + '/receive/', {})
}
function ship() {
  const current = order.value
  if (!current) return
  return command('order.ship', '/ops/orders/' + props.no + '/ship/', {
    carrier: carrier.value,
    tracking_no: tracking.value,
    expected_version: current.version,
  })
}
function startPay() {
  return command('payment.create', '/payments/', { order_no: props.no })
}
function simulate(outcome: 'success' | 'failed') {
  const payment = order.value?.payment_summary
  if (!payment) return
  return command(
    'payment.simulate',
    '/payments/' + payment.pay_no + '/simulate/',
    { outcome },
  )
}
function visible() {
  if (!document.hidden && !busy.value) load()
}
onMounted(() => {
  load()
  document.addEventListener('visibilitychange', visible)
  timer = setInterval(() => (now.value = Date.now()), 1000)
})
onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', visible)
})
</script>
<template>
  <section class="catalog order-detail">
    <router-link class="order-detail__back" :to="ops ? '/ops/orders' : '/orders'"><span aria-hidden="true">←</span> 返回订单列表</router-link>
    <header class="order-detail__header"><div><p class="catalog__eyebrow">{{ ops ? 'FULFILLMENT DETAIL' : 'ORDER DETAIL' }}</p><h1>订单详情</h1></div><button class="catalog-button catalog-button--secondary" :disabled="busy || loading" @click="load">{{ loading ? '正在核对…' : '刷新状态' }}</button></header>
    <div v-if="error" class="order-detail__notice" role="alert">{{ error }}</div>
    <div v-if="loading && !order" class="catalog__state" role="status"><span class="catalog__spinner" aria-hidden="true" />正在核对订单状态…</div>

    <article v-if="order" class="order">
      <section class="order__overview">
        <div><span class="order-status" :class="`order-status--${order.status}`">{{ statusNames[order.status] || '状态更新中' }}</span><h2>{{ statusNames[order.status] || '状态更新中' }}</h2><p>订单号 {{ no }}</p><p v-if="order.status === 'pending'" class="order__expiry">付款期限 {{ new Date(order.expires_at).toLocaleString() }}{{ now >= Date.parse(order.expires_at) ? '（已到期）' : '' }}</p></div>
        <div class="order__amount"><small>订单应付</small><strong class="siq-price"><span>¥</span>{{ order.payable_amount }}</strong><small>金额以订单快照为准</small></div>
      </section>

      <div class="order__grid">
        <div class="order__main">
          <section class="order__card">
            <header><span>01</span><h3>商品明细</h3></header>
            <ul class="order__items"><li v-for="i in order.items" :key="i.sku_id"><div><strong>{{ i.title }}</strong><span>{{ i.label }} · ¥{{ i.unit_price }} × {{ i.quantity }}</span></div></li></ul>
            <dl class="order__price-lines"><div><dt>商品合计</dt><dd>¥{{ order.goods_amount }}</dd></div><div><dt>配送费</dt><dd>¥{{ order.freight_amount }}</dd></div><div v-if="order.coupon_snapshot"><dt>优惠 · {{ order.coupon_snapshot.name }}</dt><dd>已减 ¥{{ order.discount_amount }}</dd></div><div><dt>应付金额</dt><dd>¥{{ order.payable_amount }}</dd></div></dl>
          </section>

          <section class="order__card">
            <header><span>02</span><h3>收货与配送</h3></header>
            <div class="order__address"><strong>{{ order.address_snapshot.recipient }} · {{ order.address_snapshot.phone }}</strong><p>{{ order.address_snapshot.province }}{{ order.address_snapshot.city }}{{ order.address_snapshot.district }}{{ order.address_snapshot.detail }}</p></div>
            <p v-if="order.shipment" class="order__shipment"><span>配送信息</span><strong>{{ order.shipment.carrier }} · {{ order.shipment.tracking_no }}</strong></p>
          </section>

          <section class="order__card order__actions">
            <header><span>03</span><h3>订单操作</h3></header>
            <router-link v-if="!ops && order.allowed_actions.includes('review')" class="order__review-link" :to="'/orders/' + no + '/review'">评价商品与查看审核结果 <span aria-hidden="true">→</span></router-link>
            <div v-if="unresolved" class="order__recovery"><div><strong>上次操作结果待确认</strong><p>核对原操作后再继续，避免重复执行。</p></div><button class="catalog-button catalog-button--primary" :disabled="busy" @click="command(unresolved.action, unresolved.path, unresolved.data)">核对上次操作结果</button></div>
            <div v-else class="order__action-groups">
              <section v-if="order.allowed_actions.includes('pay') && now < Date.parse(order.expires_at)" class="order__payment"><div><h4>模拟支付</h4><p>本次仅演示付款流程，不收取费用。</p></div><div v-if="order.payment_summary?.status === 'init'" class="order__buttons"><button class="catalog-button catalog-button--primary" :disabled="busy" @click="simulate('success')">模拟付款成功</button><button class="catalog-button catalog-button--secondary" :disabled="busy" @click="simulate('failed')">模拟付款失败</button></div><div v-else class="order__buttons"><p v-if="order.payment_summary?.status === 'failed'" role="alert">上次模拟付款失败，可重新尝试。</p><button class="catalog-button catalog-button--primary" :disabled="busy" @click="startPay">进入模拟支付</button></div></section>
              <div class="order__buttons">
                <button v-if="order.allowed_actions.includes('cancel') && confirm !== 'cancel'" class="catalog-button catalog-button--secondary order__danger" :disabled="busy" @click="confirm = 'cancel'">取消订单</button>
                <button v-if="order.allowed_actions.includes('cancel') && confirm === 'cancel'" class="catalog-button catalog-button--primary order__danger" :disabled="busy" @click="cancel">确认取消并释放库存</button>
                <button v-if="order.allowed_actions.includes('receive') && confirm !== 'receive'" class="catalog-button catalog-button--primary" :disabled="busy" @click="confirm = 'receive'">确认收货</button>
                <button v-if="order.allowed_actions.includes('receive') && confirm === 'receive'" class="catalog-button catalog-button--primary" :disabled="busy" @click="receive">已收到商品，完成订单</button>
              </div>
              <form v-if="order.allowed_actions.includes('ship')" class="draft order__ship-form" @submit.prevent="ship"><div><h4>确认整单发货</h4><p>请再次核对收货信息，承运商与物流单号均须填写。</p></div><label>承运商<input v-model.trim="carrier" required maxlength="50"></label><label>物流单号<input v-model.trim="tracking" required maxlength="100"></label><button class="catalog-button catalog-button--primary" :disabled="busy">确认整单发货</button></form>
              <p v-if="!order.allowed_actions.length" class="order__no-actions">当前状态没有可执行操作，可刷新查看订单进展。</p>
            </div>
          </section>
        </div>

        <aside class="order__card order__timeline">
          <header><span>04</span><h3>订单进度</h3></header>
          <ol><li v-for="e in order.events" :key="e.type"><i aria-hidden="true" /><div><strong>{{ events[e.type] || e.type }}</strong><time :datetime="e.at">{{ new Date(e.at).toLocaleString() }}</time><small v-if="e.reason === 'timeout'">订单因超时关闭</small></div></li></ol>
        </aside>
      </div>
    </article>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
.order-detail__back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  margin-bottom: 16px;
  color: var(--mall-text-secondary);
  font-size: 13px;
  text-decoration: none;
}
.order-detail__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}
.order-detail__header h1 {
  margin: 8px 0 0;
  font-size: clamp(30px, 4vw, 40px);
  font-weight: 600;
}
.order-detail__notice {
  margin-bottom: 18px;
  padding: 14px 16px;
  border: 1px solid rgb(180 35 24 / 18%);
  border-radius: var(--mall-radius-md);
  color: var(--mall-color-danger);
  background: #fff7f5;
}
.order {
  overflow-wrap: anywhere;
}
.order__overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  margin-bottom: 20px;
  padding: 28px 30px;
  border-radius: var(--mall-radius-lg);
  color: #fff;
  background: var(--mall-color-primary);
  box-shadow: var(--mall-shadow-sm);
}
.order-status {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 2px 10px;
  border-radius: var(--mall-radius-pill);
  color: var(--mall-color-primary);
  background: #fff;
  font-size: 10px;
  font-weight: 650;
}
.order__overview h2 {
  margin: 13px 0 8px;
  font-size: 28px;
  font-weight: 550;
}
.order__overview p {
  margin: 0;
  color: rgb(255 255 255 / 68%);
  font-size: 12px;
}
.order__overview .order__expiry {
  margin-top: 6px;
  color: #f8dfb6;
}
.order__amount {
  display: grid;
  flex-shrink: 0;
  justify-items: end;
}
.order__amount small {
  color: rgb(255 255 255 / 62%);
  font-size: 10px;
}
.order__amount strong {
  margin: 4px 0;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -0.035em;
}
.order__amount strong span {
  margin-right: 4px;
  font-size: 17px;
}
.order__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 310px;
  gap: 20px;
  align-items: start;
}
.order__main {
  display: grid;
  gap: 18px;
  min-width: 0;
}
.order__card {
  padding: 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: var(--mall-surface);
}
.order__card > header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.order__card > header > span {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 50%;
  color: var(--mall-color-primary);
  background: var(--mall-color-primary-light);
  font-size: 9px;
  font-weight: 650;
}
.order__card > header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.order__items {
  margin: 0;
  padding: 0;
  list-style: none;
}
.order__items li {
  padding: 12px 0;
  border-top: 1px solid var(--mall-border);
}
.order__items strong,
.order__items span {
  display: block;
}
.order__items strong {
  font-size: 14px;
  font-weight: 550;
}
.order__items span {
  margin-top: 4px;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.order__price-lines {
  margin: 12px 0 0;
  padding-top: 10px;
  border-top: 1px solid var(--mall-border);
}
.order__price-lines > div {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 6px 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.order__price-lines dd {
  margin: 0;
  color: var(--mall-text);
  font-variant-numeric: tabular-nums;
}
.order__price-lines > div:last-child {
  margin-top: 5px;
  padding-top: 12px;
  border-top: 1px solid var(--mall-border);
  color: var(--mall-text);
  font-weight: 600;
}
.order__price-lines > div:last-child dd {
  color: var(--mall-color-primary);
  font-size: 17px;
}
.order__address strong {
  font-size: 14px;
}
.order__address p {
  margin: 7px 0 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
  line-height: 1.75;
}
.order__shipment {
  display: grid;
  gap: 5px;
  margin: 18px 0 0;
  padding: 13px 15px;
  border-radius: var(--mall-radius-sm);
  background: var(--mall-color-primary-light);
}
.order__shipment span {
  color: var(--mall-text-secondary);
  font-size: 10px;
}
.order__shipment strong {
  color: var(--mall-color-primary);
  font-size: 12px;
}
.order__review-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  text-decoration: none;
}
.order__recovery {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-radius: var(--mall-radius-sm);
  background: #fbf5e9;
}
.order__recovery strong {
  color: var(--mall-color-warning);
}
.order__recovery p {
  margin: 4px 0 0;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.order__action-groups {
  display: grid;
  gap: 16px;
}
.order__payment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-radius: var(--mall-radius-sm);
  background: var(--mall-color-primary-light);
}
.order__payment h4,
.order__ship-form h4 {
  margin: 0;
  font-size: 14px;
}
.order__payment p,
.order__ship-form p {
  margin: 4px 0 0;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.order__buttons {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.order__buttons p {
  flex-basis: 100%;
  margin: 0;
}
.order__danger {
  color: var(--mall-color-danger) !important;
}
.order__ship-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 0 !important;
  padding: 18px !important;
}
.order__ship-form > div,
.order__ship-form > button {
  grid-column: 1 / -1;
}
.order__ship-form label {
  margin: 0 !important;
  font-size: 11px;
}
.order__no-actions {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.order__timeline {
  position: sticky;
  top: calc(var(--mall-header-height) + 24px);
}
.order__timeline ol {
  margin: 0;
  padding: 0;
  list-style: none;
}
.order__timeline li {
  position: relative;
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 12px;
  padding: 0 0 24px;
}
.order__timeline li:not(:last-child)::before {
  position: absolute;
  top: 12px;
  bottom: 0;
  left: 5px;
  width: 1px;
  background: var(--mall-border);
  content: '';
}
.order__timeline li > i {
  position: relative;
  z-index: 1;
  width: 11px;
  height: 11px;
  margin-top: 4px;
  border: 3px solid var(--mall-color-primary-light);
  border-radius: 50%;
  background: var(--mall-color-primary);
}
.order__timeline li strong,
.order__timeline li time,
.order__timeline li small {
  display: block;
}
.order__timeline li strong {
  font-size: 13px;
  font-weight: 550;
}
.order__timeline li time,
.order__timeline li small {
  margin-top: 4px;
  color: var(--mall-text-secondary);
  font-size: 10px;
}
@media (max-width: 950px) {
  .order__grid {
    grid-template-columns: 1fr;
  }
  .order__timeline {
    position: static;
  }
}
@media (max-width: 650px) {
  .order__overview {
    align-items: flex-start;
    flex-direction: column;
    padding: 24px;
  }
  .order__amount {
    justify-items: start;
  }
  .order__card {
    padding: 20px;
  }
  .order__payment,
  .order__recovery {
    align-items: flex-start;
    flex-direction: column;
  }
  .order__ship-form {
    grid-template-columns: 1fr;
  }
  .order__ship-form > div,
  .order__ship-form > button {
    grid-column: 1;
  }
}
</style>
