<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getOrder, pendingCommand, statusNames, submitCommand } from '@/api/orders'
const props = defineProps({ no: { type: String, required: true }, ops: Boolean })
const order = ref(null),
  error = ref(''),
  busy = ref(false),
  loading = ref(false),
  carrier = ref(''),
  tracking = ref(''),
  confirm = ref(''),
  now = ref(Date.now())
const unresolved = ref(null)
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
let timer
const events = {
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
    order.value = await getOrder(props.no, props.ops)
    checkPending()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function command(action, path, data) {
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
    error.value = e.message
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
  return command('order.ship', '/ops/orders/' + props.no + '/ship/', {
    carrier: carrier.value,
    tracking_no: tracking.value,
    expected_version: order.value.version,
  })
}
function startPay() {
  return command('payment.create', '/payments/', { order_no: props.no })
}
function simulate(outcome) {
  return command(
    'payment.simulate',
    '/payments/' + order.value.payment_summary.pay_no + '/simulate/',
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
  <section class="catalog">
    <router-link :to="ops ? '/ops/orders' : '/orders'">返回订单列表</router-link>
    <h1>订单详情</h1>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="loading">正在核对订单状态…</p>
    <button :disabled="busy || loading" @click="load">刷新状态</button>
    <article v-if="order" class="order">
      <h2>{{ statusNames[order.status] || '状态更新中' }}</h2>
      <p>订单号 {{ no }}</p>
      <p v-if="order.status === 'pending'">
        付款期限 {{ new Date(order.expires_at).toLocaleString()
        }}{{ now >= Date.parse(order.expires_at) ? '（已到期）' : '' }}
      </p>
      <h3>商品明细</h3>
      <p v-for="i in order.items" :key="i.sku_id">
        {{ i.title }} · {{ i.label }}　¥{{ i.unit_price }} × {{ i.quantity }}
      </p>
      <p>
        商品 ¥{{ order.goods_amount }}　配送 ¥{{ order.freight_amount }}　应付
        <strong>¥{{ order.payable_amount }}</strong>
      </p>
      <h3>收货信息</h3>
      <p>{{ order.address_snapshot.recipient }} · {{ order.address_snapshot.phone }}</p>
      <p>
        {{ order.address_snapshot.province }}{{ order.address_snapshot.city
        }}{{ order.address_snapshot.district }}{{ order.address_snapshot.detail }}
      </p>
      <p v-if="order.shipment">
        配送：{{ order.shipment.carrier }} · {{ order.shipment.tracking_no }}
      </p>
      <button
        v-if="unresolved"
        :disabled="busy"
        @click="command(unresolved.action, unresolved.path, unresolved.data)"
      >
        核对上次操作结果
      </button>
      <div v-else>
        <section v-if="order.allowed_actions.includes('pay') && now < Date.parse(order.expires_at)">
          <h3>模拟支付</h3>
          <p>本次仅演示付款流程，不收取费用。</p>
          <template v-if="order.payment_summary?.status === 'init'">
            <button :disabled="busy" @click="simulate('success')">模拟付款成功</button><button :disabled="busy" @click="simulate('failed')">模拟付款失败</button>
          </template>
          <template v-else>
            <p v-if="order.payment_summary?.status === 'failed'">上次模拟付款失败，可重新尝试。</p>
            <button :disabled="busy" @click="startPay">进入模拟支付</button>
          </template>
        </section>
        <button
          v-if="order.allowed_actions.includes('cancel') && confirm !== 'cancel'"
          :disabled="busy"
          @click="confirm = 'cancel'"
        >
          取消订单
        </button>
        <button
          v-if="order.allowed_actions.includes('cancel') && confirm === 'cancel'"
          :disabled="busy"
          @click="cancel"
        >
          确认取消并释放库存
        </button>
        <button
          v-if="order.allowed_actions.includes('receive') && confirm !== 'receive'"
          :disabled="busy"
          @click="confirm = 'receive'"
        >
          确认收货
        </button>
        <button
          v-if="order.allowed_actions.includes('receive') && confirm === 'receive'"
          :disabled="busy"
          @click="receive"
        >
          已收到商品，完成订单
        </button>
        <form v-if="order.allowed_actions.includes('ship')" class="draft" @submit.prevent="ship">
          <label>承运商<input v-model.trim="carrier" required maxlength="50"></label><label>物流单号<input v-model.trim="tracking" required maxlength="100"></label><button :disabled="busy">确认整单发货</button>
        </form>
      </div>
      <h3>订单进度</h3>
      <ol>
        <li v-for="e in order.events" :key="e.type">
          {{ events[e.type] || e.type }} · {{ new Date(e.at).toLocaleString()
          }}{{ e.reason === 'timeout' ? '（超时关闭）' : '' }}
        </li>
      </ol>
    </article>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
.order {
  margin-top: 16px;
  overflow-wrap: anywhere;
}
.order button {
  margin: 6px 8px 6px 0;
}
.order li {
  margin: 8px 0;
}
</style>
