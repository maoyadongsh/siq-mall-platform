<script setup>
import { ref, watch } from 'vue'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const props = defineProps({ sku: { type: Object, required: true } })
const emit = defineEmits(['changed'])
const user = useUserStore()
const label = ref(''),
  price = ref(''),
  editReason = ref(''),
  delta = ref(1),
  stockReason = ref('')
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  history = ref(null),
  historyPage = ref(1)
const key = 'siq.stock.' + user.profile.id + '.' + props.sku.id
const saved = sessionStorage.getItem(key)
const pending = ref(saved ? JSON.parse(saved) : null)
watch(
  () => props.sku,
  (s) => {
    label.value = s.label
    price.value = s.price
  },
  { immediate: true },
)
const path = '/ops/skus/' + props.sku.id + '/'
function begin() {
  busy.value = true
  error.value = ''
  notice.value = ''
}
function failed(e) {
  error.value = e.response?.data?.errors?.[0]?.detail || e.message
}

async function edit() {
  if (busy.value) return
  begin()
  try {
    const s = await request.patch(path, {
      label: label.value,
      price: price.value,
      reason: editReason.value,
      expected_version: props.sku.version,
    })
    emit('changed', s)
    editReason.value = ''
    notice.value = '规格已保存'
  } catch (e) {
    failed(e)
  } finally {
    busy.value = false
  }
}

async function records(page = 1) {
  try {
    history.value = await request.get(path + 'stock-adjustments/', { params: { page } })
    historyPage.value = page
  } catch (e) {
    failed(e)
  }
}
function clearPending() {
  sessionStorage.removeItem(key)
  pending.value = null
}
async function adjust() {
  if (busy.value) return
  begin()
  try {
    if (!pending.value) {
      const op = {
        key: crypto.randomUUID(),
        data: {
          delta: delta.value,
          reason: stockReason.value,
          expected_version: props.sku.version,
        },
      }
      sessionStorage.setItem(key, JSON.stringify(op))
      pending.value = op
    }
    const op = pending.value
    const row = await request.post(path + 'stock-adjustments/', op.data, {
      headers: { 'Idempotency-Key': op.key },
    })
    clearPending()
    // 延迟重放可能返回较早的流水，不能倒退已加载的库存版本。
    if (props.sku.version === op.data.expected_version)
      emit('changed', {
        ...props.sku,
        available_stock: row.after,
        version: op.data.expected_version + 1,
      })
    notice.value = '已登记库存流水 #' + row.id
    stockReason.value = ''
    await records()
  } catch (e) {
    if ([400, 403, 404, 409].includes(e.response?.status)) clearPending()
    failed(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <article class="variant-editor">
    <h3>{{ sku.label }}</h3>
    <p>可售库存 {{ sku.available_stock }}</p>
    <form class="draft" @submit.prevent="edit">
      <label>规格名称<input v-model.trim="label" required maxlength="80"></label>
      <label>售价（元）<input v-model="price" type="number" required min="0" step=".01"></label>
      <label>修改原因<input v-model.trim="editReason" required maxlength="200"></label>
      <button :disabled="busy || !!pending">保存规格</button>
    </form>
    <form v-if="!pending" class="draft" @submit.prevent="adjust">
      <label>库存调整量（增加填正数，扣减填负数）<input
        v-model.number="delta"
        type="number"
        required
        step="1"
      ></label>
      <label>调整原因<input v-model.trim="stockReason" required maxlength="200"></label>
      <button :disabled="busy || delta === 0">登记库存调整</button>
    </form>
    <button v-else :disabled="busy" @click="adjust">确认上次库存调整结果</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <button type="button" @click="records()">查看库存流水</button>
    <template v-if="history">
      <p v-if="!history.count">暂无人工调整记录</p>
      <ol>
        <li v-for="r in history.results" :key="r.id">
          {{ new Date(r.created_at).toLocaleString() }} · {{ r.operator }} · {{ r.reason }}：{{
            r.before
          }}
          → {{ r.after }}（{{ r.delta > 0 ? '+' : '' }}{{ r.delta }}）
        </li>
      </ol>
      <button v-if="historyPage > 1" @click="records(historyPage - 1)">上一页</button>
      <button v-if="historyPage < history.total_pages" @click="records(historyPage + 1)">
        下一页
      </button>
    </template>
  </article>
</template>
