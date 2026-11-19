<script setup lang="ts">
import { ref, watch } from 'vue'
import { getOrders, statusNames } from '@/api/orders'
import type { OrderSummary, Page } from '@/types/models'
import request from '@/utils/request'
import { messageOf } from '@/utils/errors'

interface OrderActivity {
  order_no: string
  type: string
  occurred_at: string
}

const activity = ref<OrderActivity[] | null>(null),
  feedError = ref('')
const eventNames: Record<string, string> = {
  'order.created': '下单',
  'order.paid': '模拟付款',
  'order.shipped': '发货',
  'order.completed': '收货',
  'order.canceled': '取消',
}
async function readFeed(event: Event) {
  const target = event.target as HTMLDetailsElement | null
  if (!target?.open) return
  try {
    feedError.value = ''
    activity.value = await request.get<OrderActivity[]>('/ops/order-activities/')
  } catch (e) {
    feedError.value = messageOf(e)
  }
}
const props = defineProps({ ops: Boolean })
const status = ref(''),
  number = ref(''),
  page = ref(1),
  data = ref<Page<OrderSummary> | null>(null),
  error = ref(''),
  busy = ref(false)
let seq = 0
async function load(n = 1) {
  const id = ++seq
  busy.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: n }
    if (status.value) params.status = status.value
    if (number.value) params.order_no = number.value
    const result = await getOrders(Boolean(props.ops), params)
    if (id === seq) {
      data.value = result
      page.value = n
    }
  } catch (e) {
    if (id === seq) error.value = messageOf(e)
  } finally {
    if (id === seq) busy.value = false
  }
}
watch(
  () => props.ops,
  () => load(),
  { immediate: true },
)
</script>
<template>
  <section class="catalog order-list" :class="{ 'order-list--ops': ops }">
    <header class="order-list__header"><div><p class="catalog__eyebrow">{{ ops ? 'FULFILLMENT OPERATIONS' : 'YOUR ORDERS' }}</p><h1>{{ ops ? '订单履约' : '我的订单' }}</h1><p>{{ ops ? '核对订单快照与状态，完成权限内履约操作。' : '每一次选择与每一步进度，都清楚保留在这里。' }}</p></div></header>

    <details v-if="ops" class="order-list__activity" @toggle="readFeed">
      <summary><span>最近履约动态</span><small>查看已投递的真实订单事件</small></summary>
      <p v-if="feedError" role="alert">{{ feedError }}</p>
      <p v-else-if="!activity">正在读取…</p>
      <p v-else-if="!activity.length">暂无已投递动态</p>
      <ul v-else><li v-for="a in activity" :key="a.order_no + a.type"><strong>{{ eventNames[a.type] }}</strong><span>{{ new Date(a.occurred_at).toLocaleString() }}</span><router-link :to="'/ops/orders/' + a.order_no">{{ a.order_no }}</router-link></li></ul>
    </details>

    <form class="search order-list__filters" @submit.prevent="load()">
      <label><span>订单状态</span><select v-model="status"><option value="">全部状态</option><option v-for="(s, k) in statusNames" :key="k" :value="k">{{ s }}</option></select></label>
      <label v-if="ops"><span>订单号</span><input v-model.trim="number" placeholder="输入完整订单号"></label>
      <button class="catalog-button catalog-button--primary">查询订单</button>
    </form>

    <div v-if="error" class="order-list__notice order-list__notice--error" role="alert"><span>{{ error }}</span><button @click="load(page)">重试</button></div>
    <div v-if="busy && !data" class="catalog__state" role="status"><span class="catalog__spinner" aria-hidden="true" />正在读取订单…</div>
    <p v-else-if="busy" class="order-list__refreshing" role="status">正在更新订单列表…</p>

    <template v-if="data">
      <div v-if="!data.results.length && !error" class="order-list__empty"><span aria-hidden="true">S</span><h2>暂无符合条件的订单</h2><p>可以调整状态筛选，或稍后再来查看。</p></div>
      <div v-else-if="ops" class="order-list__table-wrap">
        <table class="order-list__table"><thead><tr><th>状态</th><th>订单号</th><th>创建时间</th><th>应付金额</th><th>操作</th></tr></thead><tbody><tr v-for="o in data.results" :key="o.order_no"><td><span class="order-status" :class="`order-status--${o.status}`">{{ statusNames[o.status] || '状态更新中' }}</span></td><td><strong>{{ o.order_no }}</strong></td><td>{{ new Date(o.created_at).toLocaleString() }}</td><td class="siq-price">¥{{ o.payable_amount }}</td><td><router-link :to="'/ops/orders/' + o.order_no">查看并处理 <span aria-hidden="true">→</span></router-link></td></tr></tbody></table>
      </div>
      <div v-else class="order-list__cards">
        <article v-for="o in data.results" :key="o.order_no">
          <header><span class="order-status" :class="`order-status--${o.status}`">{{ statusNames[o.status] || '状态更新中' }}</span><time :datetime="o.created_at">{{ new Date(o.created_at).toLocaleString() }}</time></header>
          <div><small>订单号</small><strong>{{ o.order_no }}</strong></div>
          <footer><p><small>应付金额</small><strong class="siq-price">¥{{ o.payable_amount }}</strong></p><router-link :to="'/orders/' + o.order_no">查看订单 <span aria-hidden="true">→</span></router-link></footer>
        </article>
      </div>
      <nav v-if="data.total_pages > 1" class="catalog__pagination" aria-label="订单分页"><button class="catalog-button catalog-button--secondary" :disabled="page <= 1 || busy" @click="load(page - 1)">上一页</button><span>第 {{ page }} 页，共 {{ data.total_pages }} 页</span><button class="catalog-button catalog-button--secondary" :disabled="page >= data.total_pages || busy" @click="load(page + 1)">下一页</button></nav>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
.order-list__header {
  margin-bottom: 28px;
}
.order-list__header h1 {
  margin: 8px 0 10px;
  font-size: clamp(30px, 4vw, 40px);
  font-weight: 600;
}
.order-list__header p:last-child {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 14px;
}
.order-list__activity {
  margin-bottom: 18px;
  padding: 0 18px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  background: var(--mall-surface);
}
.order-list__activity summary {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 52px;
  cursor: pointer;
}
.order-list__activity summary span {
  font-weight: 600;
}
.order-list__activity summary small {
  color: var(--mall-text-secondary);
}
.order-list__activity > p {
  padding: 0 0 16px;
  color: var(--mall-text-secondary);
}
.order-list__activity ul {
  margin: 0;
  padding: 0 0 12px;
  list-style: none;
}
.order-list__activity li {
  display: grid;
  grid-template-columns: 100px 180px minmax(0, 1fr);
  gap: 16px;
  padding: 10px 0;
  border-top: 1px solid var(--mall-border);
  font-size: 12px;
}
.order-list__activity li span {
  color: var(--mall-text-secondary);
}
.order-list__filters {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  background: rgb(255 255 255 / 65%);
}
.order-list__filters label {
  display: grid;
  gap: 6px;
  min-width: 180px;
}
.order-list__filters label > span {
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.order-list__notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: var(--mall-radius-md);
}
.order-list__notice--error {
  color: var(--mall-color-danger);
  background: #fff3f1;
}
.order-list__refreshing {
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.order-list__cards {
  display: grid;
  gap: 14px;
}
.order-list__cards article {
  overflow: hidden;
  padding: 22px 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: var(--mall-surface);
  overflow-wrap: anywhere;
  transition: border-color var(--mall-motion-fast) ease, box-shadow var(--mall-motion-fast) ease;
}
.order-list__cards article:hover {
  border-color: var(--mall-border-strong);
  box-shadow: var(--mall-shadow-sm);
}
.order-list__cards article > header,
.order-list__cards article > footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.order-list__cards time {
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.order-list__cards article > div {
  display: grid;
  gap: 4px;
  margin: 20px 0;
}
.order-list__cards small {
  color: var(--mall-text-secondary);
  font-size: 10px;
}
.order-list__cards article > div strong {
  font-size: 14px;
  font-weight: 550;
}
.order-list__cards article > footer {
  padding-top: 16px;
  border-top: 1px solid var(--mall-border);
}
.order-list__cards footer p {
  margin: 0;
}
.order-list__cards footer p small,
.order-list__cards footer p strong {
  display: block;
}
.order-list__cards footer p strong {
  color: var(--mall-color-primary);
  font-size: 19px;
}
.order-list__cards footer a,
.order-list__table a {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  font-size: 13px;
  text-decoration: none;
}
.order-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 3px 11px;
  border-radius: var(--mall-radius-pill);
  color: var(--mall-text-secondary);
  background: #efefeb;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.order-status--pending {
  color: var(--mall-color-warning);
  background: #f8f0df;
}
.order-status--paid,
.order-status--shipped {
  color: var(--mall-color-primary);
  background: var(--mall-color-primary-light);
}
.order-status--completed {
  color: var(--mall-color-success);
  background: #eaf3ed;
}
.order-status--canceled {
  color: var(--mall-text-secondary);
  background: #efefeb;
}
.order-list__empty {
  padding: 64px 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: rgb(255 255 255 / 55%);
  text-align: center;
}
.order-list__empty > span {
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
.order-list__empty h2 {
  margin-bottom: 10px;
  font-size: 22px;
}
.order-list__empty p {
  color: var(--mall-text-secondary);
}
.order-list__table-wrap {
  overflow-x: auto;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  background: var(--mall-surface);
}
.order-list__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.order-list__table th,
.order-list__table td {
  padding: 13px 16px;
  border-bottom: 1px solid var(--mall-border);
  text-align: left;
  white-space: nowrap;
}
.order-list__table th {
  color: var(--mall-text-secondary);
  background: #fafaf8;
  font-size: 11px;
  font-weight: 600;
}
.order-list__table tr:last-child td {
  border-bottom: 0;
}
.order-list__table td:nth-child(2) {
  min-width: 220px;
}
.order-list__table td:nth-child(2) strong {
  font-weight: 550;
}
@media (max-width: 600px) {
  .order-list__filters {
    align-items: stretch;
    flex-direction: column;
  }
  .order-list__filters label {
    min-width: 0;
  }
  .order-list__activity summary small {
    display: none;
  }
  .order-list__activity li {
    grid-template-columns: 1fr;
    gap: 3px;
  }
  .order-list__cards article {
    padding: 18px;
  }
  .order-list__cards article > header {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
}
</style>
