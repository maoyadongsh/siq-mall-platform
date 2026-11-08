<script setup>
import { onMounted, ref } from 'vue'
import request from '@/utils/request'
import SkuEditor from './SkuEditor.vue'

const props = defineProps({ id: { type: String, required: true } })
const product = ref(null)
const draft = ref({})
const file = ref(null)
const upload = ref(null)
const fileInput = ref(null)
const busy = ref(false)
const error = ref('')
const message = ref('')

function readProduct(p) {
  product.value = p
  draft.value = {
    title: p.title,
    category: p.category,
    description: p.description,
    expected_version: p.version,
  }
  file.value = null
  upload.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function reload() {
  busy.value = true
  error.value = ''
  try {
    readProduct(await request.get('/ops/products/' + props.id + '/'))
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    if (file.value && !upload.value) {
      const body = new FormData()
      body.append('file', file.value)
      upload.value = await request.post('/ops/media/', body)
    }
    const payload = { ...draft.value }
    if (upload.value) payload.cover_id = upload.value.asset_id
    readProduct(await request.patch('/ops/products/' + props.id + '/', payload))
    message.value = '商品信息已保存'
  } catch (e) {
    error.value = e.response?.data?.errors?.[0]?.detail || e.message
  } finally {
    busy.value = false
  }
}

function choose(event) {
  file.value = event.target.files[0] || null
  upload.value = null
}

async function skuChanged(row) {
  product.value.skus = product.value.skus.map((s) => s.id === row.id ? row : s)
  try {
    const latest = await request.get('/ops/products/' + props.id + '/')
    const previous = product.value
    if (latest.version < previous.version) return
    const metadataUnchanged = ['title', 'category', 'description', 'cover_url'].every(
      (key) => previous[key] === latest[key],
    )
    if (metadataUnchanged && draft.value.expected_version === previous.version) {
      draft.value.expected_version = latest.version
    }
    product.value = { ...latest, skus: previous.skus }
  } catch {
    error.value = '规格操作已登记，商品版本读取失败。请刷新后核对。'
  }
}
onMounted(reload)
</script>
<template>
  <section class="catalog">
    <router-link to="/ops/products">返回商品管理</router-link>
    <h1>维护商品</h1>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <button :disabled="busy" @click="reload">读取最新商品并重置表单</button>
    <template v-if="product">
      <form class="draft" @submit.prevent="save">
        <label>商品名称<input v-model.trim="draft.title" maxlength="120" required></label>
        <label>分类<input v-model.trim="draft.category" maxlength="50" required></label>
        <label>描述<textarea v-model="draft.description" maxlength="5000" /></label>
        <img
          v-if="product.cover_url"
          class="product-cover"
          :src="product.cover_url"
          :alt="product.title"
        >
        <label>商品主图（JPEG、PNG、WebP，最大5MB）<input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          @change="choose"
        ></label>
        <button :disabled="busy">保存商品信息</button>
      </form>
      <h2>规格与库存</h2>
      <SkuEditor v-for="s in product.skus" :key="s.id" :sku="s" @changed="skuChanged" />
    </template>
  </section>
</template>
<style src="./catalog.css"></style>
