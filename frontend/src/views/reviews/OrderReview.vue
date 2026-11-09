<script setup>
import './reviews.css'
import { computed, onMounted, reactive, ref } from 'vue'
import { getOrder } from '@/api/orders'
import { mine, submitReview, reviewStatuses } from '@/api/reviews'
const props = defineProps({ no: { type: String, required: true } })
const order = ref(null),
  reviews = ref([]),
  forms = reactive({}),
  error = ref(''),
  loading = ref(false),
  sending = ref(''),
  notice = ref('')
const byItem = computed(() => Object.fromEntries(reviews.value.map((r) => [r.order_item_id, r])))
const length = (s) => [...s.trim()].length
async function load() {
  error.value = ''
  loading.value = true
  try {
    const [o, rows] = await Promise.all([
      getOrder(props.no),
      mine({ order_no: props.no, page_size: 100 }),
    ])
    order.value = o
    reviews.value = rows.results
    for (const i of o.items) forms[i.order_item_id] ??= { rating: 0, content: '' }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function send(i) {
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
    error.value = e.response?.data?.errors?.[0]?.detail || e.message
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
