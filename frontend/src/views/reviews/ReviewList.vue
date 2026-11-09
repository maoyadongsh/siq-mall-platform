<script setup>
import './reviews.css'
import { ref, watch } from 'vue'
import { queue, mine, moderateReview, reviewStatuses } from '@/api/reviews'
const props = defineProps({ ops: Boolean })
const data = ref(null),
  status = ref(''),
  productId = ref(''),
  error = ref(''),
  loading = ref(false),
  busy = ref(false)
const target = ref(null),
  action = ref(''),
  reason = ref(''),
  notice = ref('')
const verbs = { approve: '公开', reject: '拒绝', hide: '隐藏' }
let seq = 0
async function load(n = 1) {
  const ticket = ++seq
  loading.value = true
  error.value = ''
  try {
    const out = props.ops
      ? await queue({
          page: n,
          status: status.value || undefined,
          product_id: productId.value || undefined,
        })
      : await mine({ page: n })
    if (ticket === seq) {
      data.value = out
      target.value = null
    }
  } catch (e) {
    if (ticket === seq) error.value = e.message
  } finally {
    if (ticket === seq) loading.value = false
  }
}
function prepare(r, a) {
  target.value = r
  action.value = a
  reason.value = ''
  error.value = ''
  notice.value = ''
}
async function apply() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await moderateReview(target.value, action.value, reason.value.trim())
    notice.value = '审核已保存'
    await load()
  } catch (e) {
    error.value = e.response?.data?.errors?.[0]?.detail || e.message
  } finally {
    busy.value = false
  }
}
watch(
  () => props.ops,
  () => {
    status.value = props.ops ? 'pending' : ''
    load()
  },
  { immediate: true },
)
</script>
<template>
  <section class="catalog">
    <h1>{{ ops ? '评价审核' : '我的评价' }}</h1>
    <form v-if="ops" class="search" @submit.prevent="load()">
      <label>审核状态
        <select v-model="status">
          <option value="">全部</option>
          <option v-for="(v, k) in reviewStatuses" :key="k" :value="k">{{ v }}</option>
        </select></label>
      <label>商品编号 <input v-model.trim="productId" inputmode="numeric" pattern="[0-9]*"></label><button :disabled="busy">筛选</button>
    </form>
    <p v-if="error" role="alert">
      {{ error }} <button :disabled="busy" @click="load()">刷新列表</button>
    </p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="loading">正在读取评价…</p>
    <template v-else-if="data">
      <p v-if="!data.results.length">{{ ops ? '当前筛选下没有评价。' : '还没有提交过评价。' }}</p>
      <article v-for="r in data.results" :key="r.id" class="review-section">
        <small>{{ reviewStatuses[r.status] }} · {{ new Date(r.created_at).toLocaleString() }}</small>
        <h2>{{ r.product_title }} · {{ r.sku_label }}</h2>
        <strong>{{ r.rating }} 星</strong>
        <p class="review-text">{{ r.content }}</p>
        <p v-if="r.moderation_reason">审核说明：{{ r.moderation_reason }}</p>
        <template v-if="ops">
          <p>
            商品编号 {{ r.product_id }} · 订单项 {{ r.order_item_id }} · 购买 {{ r.quantity }} 件
          </p>
          <template v-if="target?.id !== r.id">
            <button v-if="r.status === 'pending'" @click="prepare(r, 'approve')">公开评价</button>
            <button v-if="r.status === 'pending'" @click="prepare(r, 'reject')">拒绝评价</button><button v-if="r.status === 'approved'" @click="prepare(r, 'hide')">
              隐藏评价
            </button>
          </template>
          <form v-else class="draft" @submit.prevent="apply">
            <label>审核原因{{ action === 'approve' ? '（可选）' : '（必填）'
            }}<input v-model.trim="reason" :required="action !== 'approve'" maxlength="200"></label>
            <button type="button" :disabled="busy" @click="target = null">取消</button><button :disabled="busy || (action !== 'approve' && !reason.trim())">
              确认{{ verbs[action] }}
            </button>
          </form>
        </template><router-link v-else :to="'/orders/' + r.order_no + '/review'">查看订单评价</router-link>
      </article>
      <nav v-if="data.total_pages > 1">
        <button :disabled="busy || data.page <= 1" @click="load(data.page - 1)">上一页</button>{{ data.page }} / {{ data.total_pages
        }}<button :disabled="busy || data.page >= data.total_pages" @click="load(data.page + 1)">
          下一页
        </button>
      </nav>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
