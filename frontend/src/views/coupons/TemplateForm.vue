<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'
const props = defineProps({ source: { type: Object, default: null } })
const emit = defineEmits(['saved', 'cancel'])
const s = props.source
const localDate = (v) => {
  const d = new Date(v)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19)
}
const from = localDate(Date.now() - 60000),
  end = localDate(Date.now() + 7 * 86400000)
const form = reactive({
  name: s?.name || '',
  type: s?.type || 'fixed',
  threshold_amount: s?.threshold_amount || '129.00',
  reduction_amount: s?.reduction_amount || '20.00',
  rate: (s?.discount_bps || 1000) / 100,
  cap_amount: s?.cap_amount || '20.00',
  scope: s?.scope || 'all',
  product_ids: [...(s?.product_ids || [])],
  total: s?.total || 50,
  per_user_limit: s?.per_user_limit || 1,
  start_at: s ? localDate(s.start_at) : from,
  end_at: s ? localDate(s.end_at) : end,
  claim_start_at: s ? localDate(s.claim_start_at) : from,
  claim_end_at: s ? localDate(s.claim_end_at) : end,
})
const error = ref(''),
  busy = ref(false),
  query = ref(''),
  products = ref(null)
async function find(n = 1) {
  try {
    products.value = await request.get('/products/', { params: { q: query.value, page: n } })
  } catch (e) {
    error.value = e.message
  }
}
async function save() {
  busy.value = true
  error.value = ''
  try {
    const { rate, ...out } = form
    const payload = {
      ...out,
      product_ids: form.scope === 'all' ? [] : form.product_ids,
      reduction_amount: form.type === 'fixed' ? form.reduction_amount : null,
      discount_bps: form.type === 'percentage' ? Math.round(rate * 100) : null,
      cap_amount: form.type === 'percentage' ? form.cap_amount : null,
    }
    for (const key of ['start_at', 'end_at', 'claim_start_at', 'claim_end_at'])
      payload[key] = new Date(form[key]).toISOString()
    if (s)
      await request.patch('/ops/coupons/' + s.id + '/', { ...payload, expected_version: s.version })
    else await request.post('/ops/coupons/', payload)
    emit('saved')
  } catch (e) {
    error.value = e.response?.data?.errors?.map((x) => x.detail).join('；') || e.message
  } finally {
    busy.value = false
  }
}
onMounted(() => {
  if (form.scope === 'products') find()
})
</script>
<template>
  <form class="draft" @submit.prevent="save">
    <label>券名称<input v-model.trim="form.name" maxlength="80" required></label>
    <label>优惠类型<select v-model="form.type">
      <option value="fixed">满减</option>
      <option value="percentage">按比例减免</option>
    </select></label>
    <label>商品金额门槛（元）<input
      v-model="form.threshold_amount"
      type="number"
      step=".01"
      min="0"
      required
    ></label>
    <label v-if="form.type === 'fixed'">减免金额（元）<input
      v-model="form.reduction_amount"
      type="number"
      step=".01"
      min=".01"
      required
    ></label>
    <template v-else>
      <label>减免比例（%）<input
        v-model.number="form.rate"
        type="number"
        step=".01"
        min=".01"
        max="100"
        required
      ></label><label>减免上限（元）<input
        v-model="form.cap_amount"
        type="number"
        min=".01"
        step=".01"
        required
      ></label>
    </template>
    <label>发行总量<input v-model.number="form.total" type="number" min="1" required></label><label>每人限领<input v-model.number="form.per_user_limit" type="number" min="1" required></label>
    <label>适用范围<select v-model="form.scope" @change="form.scope === 'products' && find()">
      <option value="all">全场商品</option>
      <option value="products">指定商品</option>
    </select></label>
    <fieldset v-if="form.scope === 'products'">
      <legend>选择适用商品（已选 {{ form.product_ids.length }}）</legend>
      <input v-model="query" aria-label="查找适用商品"><button type="button" @click="find()">
        查找
      </button>
      <label v-for="p in products?.results" :key="p.id"><input v-model="form.product_ids" type="checkbox" :value="p.id">{{ p.title }}</label>
      <button v-if="products?.page > 1" type="button" @click="find(products.page - 1)">
        上一页商品
      </button><button
        v-if="products?.page < products?.total_pages"
        type="button"
        @click="find(products.page + 1)"
      >
        下一页商品
      </button>
    </fieldset>
    <label
      v-for="(label, k) in {
        start_at: '使用开始',
        end_at: '使用截止',
        claim_start_at: '领取开始',
        claim_end_at: '领取截止',
      }"
      :key="k"
    >{{ label }}<input v-model="form[k]" type="datetime-local" step="1" required></label>
    <p v-if="error" role="alert">{{ error }}</p>
    <button type="button" @click="emit('cancel')">取消编辑</button><button :disabled="busy">保存草稿</button>
  </form>
</template>
