<script setup lang="ts">
import { onMounted, ref } from 'vue'
import request from '@/utils/request'
import { messageOf } from '@/utils/errors'
import type { Product, Sku } from '@/types/models'
import SkuEditor from './SkuEditor.vue'

interface ProductDraft {
  title: string
  category: string
  description?: string
  expected_version?: number
}

interface MediaAsset {
  asset_id: number
}

const metadataKeys = ['title', 'category', 'description', 'cover_url'] as const

function detailOf(e: unknown): string | undefined {
  return (e as { response?: { data?: { errors?: { detail?: string }[] } } }).response?.data
    ?.errors?.[0]?.detail
}

const props = defineProps({ id: { type: String, required: true } })
const product = ref<Product | null>(null)
const draft = ref<ProductDraft>({ title: '', category: '', description: '' })
const file = ref<File | null>(null)
const upload = ref<MediaAsset | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const error = ref('')
const message = ref('')

function readProduct(p: Product) {
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
    readProduct(await request.get<Product>('/ops/products/' + props.id + '/'))
  } catch (e) {
    error.value = messageOf(e)
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
      upload.value = await request.post<MediaAsset>('/ops/media/', body)
    }
    const payload: Record<string, unknown> = { ...draft.value }
    if (upload.value) payload.cover_id = upload.value.asset_id
    readProduct(await request.patch<Product>('/ops/products/' + props.id + '/', payload))
    message.value = '商品信息已保存'
  } catch (e) {
    error.value = detailOf(e) || messageOf(e)
  } finally {
    busy.value = false
  }
}

function choose(event: Event) {
  const target = event.target as HTMLInputElement
  file.value = target.files?.[0] ?? null
  upload.value = null
}

async function skuChanged(row: Sku) {
  const previous = product.value
  if (!previous) return
  previous.skus = previous.skus.map((s) => (s.id === row.id ? row : s))
  try {
    const latest = await request.get<Product>('/ops/products/' + props.id + '/')
    if ((latest.version ?? 0) < (previous.version ?? 0)) return
    const metadataUnchanged = metadataKeys.every(
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
