<script setup>
import './reviews.css'
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { publicReviews } from '@/api/reviews'
const props = defineProps({ id: { type: String, required: true } })
const data = ref(null),
  loading = ref(false),
  error = ref(''),
  lastPage = ref(1)
let seq = 0,
  timer,
  inFlight = false
async function load(page = 1, quiet = false) {
  const ticket = ++seq
  lastPage.value = page
  inFlight = true
  loading.value = !quiet
  error.value = ''
  try {
    const out = await publicReviews(props.id, page)
    if (ticket === seq) data.value = out
  } catch (e) {
    if (ticket !== seq) return
    if (page > 1 && e.response?.status === 404) return load(1)
    error.value = e.message
  } finally {
    if (ticket === seq) {
      loading.value = false
      inFlight = false
    }
  }
}
function refreshVisible() {
  if (!document.hidden && !inFlight) load(lastPage.value, true)
}
onMounted(() => {
  timer = setInterval(refreshVisible, 45000)
  document.addEventListener('visibilitychange', refreshVisible)
})
onUnmounted(() => {
  seq++
  clearInterval(timer)
  document.removeEventListener('visibilitychange', refreshVisible)
})
watch(
  () => props.id,
  () => {
    data.value = null
    load()
  },
  { immediate: true },
)
</script>
<template>
  <section class="review-section">
    <h2>买家评价</h2>
    <p v-if="loading">正在读取评价…</p>
    <p v-else-if="error" role="alert">
      {{ error }} <button @click="load(lastPage)">重新加载评价</button>
    </p>
    <template v-else-if="data">
      <p v-if="data.rating_summary.count === 0">暂无公开评价。</p>
      <template v-else>
        <p aria-live="polite">
          <strong>{{ data.rating_summary.average }} / 5</strong> ·
          {{ data.rating_summary.count }} 条公开评价
        </p>
        <article v-for="r in data.results" :key="r.id">
          <p>{{ r.author_display }} · {{ r.rating }} 星 · {{ r.sku_label }}</p>
          <p class="review-text">{{ r.content }}</p>
          <small>{{ new Date(r.created_at).toLocaleDateString() }}</small>
        </article>
      </template>
      <nav v-if="data.total_pages > 1">
        <button :disabled="data.page === 1" @click="load(data.page - 1)">上一页评价</button>{{ data.page }} / {{ data.total_pages
        }}<button :disabled="data.page === data.total_pages" @click="load(data.page + 1)">
          下一页评价
        </button>
      </nav>
    </template>
  </section>
</template>
