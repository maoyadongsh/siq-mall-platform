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
  <section class="catalog">
    <h1>{{ ops ? '订单履约' : '我的订单' }}</h1>
    <details v-if="ops" @toggle="readFeed">
      <summary>最近履约动态</summary>
      <p v-if="feedError">{{ feedError }}</p>
      <p v-else-if="!activity">正在读取…</p>
      <p v-else-if="!activity.length">暂无已投递动态</p>
      <ul v-else>
        <li v-for="a in activity" :key="a.order_no + a.type">
          {{ eventNames[a.type] }} · {{ new Date(a.occurred_at).toLocaleString() }} ·
          <router-link :to="'/ops/orders/' + a.order_no">{{ a.order_no }}</router-link>
        </li>
      </ul>
    </details>
    <form class="search" @submit.prevent="load()">
      <label>订单状态
        <select v-model="status">
          <option value="">全部</option>
          <option v-for="(s, k) in statusNames" :key="k" :value="k">{{ s }}</option>
        </select></label>
      <input v-if="ops" v-model.trim="number" aria-label="订单号" placeholder="订单号"><button>
        查询
      </button>
    </form>
    <p v-if="busy">正在读取订单…</p>
    <p v-else-if="error" role="alert">{{ error }} <button @click="load(page)">重试</button></p>
    <template v-else-if="data">
      <p v-if="!data.results.length">暂无符合条件的订单。</p>
      <article v-for="o in data.results" :key="o.order_no">
        <strong>{{ statusNames[o.status] || '状态更新中' }}</strong>
        <p>订单号 {{ o.order_no }}</p>
        <p>{{ new Date(o.created_at).toLocaleString() }} · ¥{{ o.payable_amount }}</p>
        <router-link :to="(ops ? '/ops' : '') + '/orders/' + o.order_no">查看订单</router-link>
      </article>
      <nav v-if="data.total_pages > 1">
        <button :disabled="page <= 1" @click="load(page - 1)">上一页</button>{{ page }} /
        {{ data.total_pages
        }}<button :disabled="page >= data.total_pages" @click="load(page + 1)">下一页</button>
      </nav>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
article {
  margin: 12px 0;
  overflow-wrap: anywhere;
}
select {
  min-height: 44px;
  font: inherit;
}
</style>
