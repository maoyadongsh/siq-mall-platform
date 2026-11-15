<script setup lang="ts">
import './reviews.css'
import { computed, onMounted, reactive, ref } from 'vue'
import { getOrder } from '@/api/orders'
import { mine, submitReview, reviewStatuses, type ReviewRecord } from '@/api/reviews'
import { messageOf } from '@/utils/errors'

interface OrderItem {
  order_item_id: string
  title: string
  label: string
}

interface ReviewOrder {
  status: string
  items: OrderItem[]
}

interface ReviewForm {
  rating: number
  content: string
}

const props = defineProps({ no: { type: String, required: true } })
const order = ref<ReviewOrder | null>(null),
  reviews = ref<ReviewRecord[]>([]),
  forms = reactive<Record<string, ReviewForm>>({}),
  error = ref(''),
  loading = ref(false),
  sending = ref(''),
  notice = ref('')
const byItem = computed(() => {
  const map: Record<string, ReviewRecord> = {}
  for (const review of reviews.value) map[review.order_item_id] = review
  return map
})
const length = (s: string) => [...s.trim()].length

function detailOf(error: unknown): string {
  const response = (error as { response?: { data?: { errors?: { detail?: string }[] } } }).response
  return response?.data?.errors?.[0]?.detail || messageOf(error)
}

async function load() {
  error.value = ''
  loading.value = true
  try {
    const [detail, rows] = await Promise.all([
      getOrder(props.no),
      mine({ order_no: props.no, page_size: 100 }),
    ])
    const current = detail as unknown as ReviewOrder
    order.value = current
    reviews.value = rows.results
    for (const i of current.items) forms[i.order_item_id] ??= { rating: 0, content: '' }
  } catch (e) {
    error.value = messageOf(e)
  } finally {
    loading.value = false
  }
}
async function send(i: OrderItem) {
  const id = i.order_item_id,
    f = forms[id]
  if (sending.value || !f.rating || length(f.content) < 1 || length(f.content) > 500) return
  sending.value = id
  error.value = ''
  notice.value = ''
  try {
    const r = await submitReview(id, f.rating, f.content.trim())
    reviews.value = [...reviews.value.filter((x) => x.order_item_id !== id), r]
    notice.value = '评价已提交，等待审核'
  } catch (e) {
    error.value = detailOf(e)
  } finally {
    sending.value = ''
  }
}
onMounted(load)
</script>
<template>
  <section class="catalog">
    <router-link :to="'/orders/' + no">返回订单详情</router-link>
    <h1>评价订单商品</h1>
    <p v-if="error" role="alert">
      {{ error }} <button :disabled="loading || !!sending" @click="load">核对评价状态</button>
    </p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="loading">正在核对购买记录…</p>
    <template v-else-if="order">
      <p v-if="order.status !== 'completed'">确认收货后可评价订单中的商品。</p>
      <article v-for="i in order.items" :key="i.order_item_id" class="review-section">
        <h2>{{ i.title }} · {{ i.label }}</h2>
        <template v-if="byItem[i.order_item_id]">
          <strong>{{ reviewStatuses[byItem[i.order_item_id].status] }} ·
            {{ byItem[i.order_item_id].rating }} 星</strong>
          <p class="review-text">{{ byItem[i.order_item_id].content }}</p>
          <p v-if="byItem[i.order_item_id].moderation_reason">
            审核说明：{{ byItem[i.order_item_id].moderation_reason }}
          </p>
        </template>
        <form v-else-if="order.status === 'completed'" @submit.prevent="send(i)">
          <fieldset>
            <legend>使用感受评分</legend>
            <label v-for="n in 5" :key="n" class="rating-choice"><input
              v-model="forms[i.order_item_id].rating"
              type="radio"
              :name="'rating-' + i.order_item_id"
              :value="n"
              required
            >{{ n }} 星</label>
          </fieldset>
          <label class="review-field">评价内容<textarea
            v-model="forms[i.order_item_id].content"
            maxlength="1000"
            rows="3"
            required
            placeholder="分享实际使用感受"
          />
          </label>
          <p>{{ length(forms[i.order_item_id].content) }} / 500 字</p>
          <button
            :disabled="
              !!sending ||
                !forms[i.order_item_id].rating ||
                length(forms[i.order_item_id].content) < 1 ||
                length(forms[i.order_item_id].content) > 500
            "
          >
            提交评价
          </button>
        </form>
      </article>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
