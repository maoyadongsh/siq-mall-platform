<script setup>
import { reactive, ref } from 'vue'
import request from '@/utils/request'
const emit = defineEmits(['saved'])
const sku = () => ({ label: '', price: '', available_stock: 0 })
const form = reactive({ title: '', category: '', description: '', skus: [sku()] })
const error = ref('')
const pending = ref(false)
async function save() {
  if (pending.value) return
  pending.value = true
  try {
    await request.post('/ops/products/', form)
    emit('saved')
  } catch (e) {
    error.value = e.response?.data?.errors?.map((x) => x.detail).join('；') || e.message
  } finally {
    pending.value = false
  }
}
</script>
<template>
  <form class="draft" @submit.prevent="save">
    <label>商品名称<input v-model.trim="form.title" maxlength="120" required></label>
    <label>分类<input v-model.trim="form.category" maxlength="50" required></label>
    <label>商品描述<textarea v-model="form.description" maxlength="5000" /></label>
    <fieldset v-for="(s, i) in form.skus" :key="i">
      <legend>规格 {{ i + 1 }}</legend>
      <label>规格名称<input v-model.trim="s.label" maxlength="80" required></label>
      <label>售价（元）<input v-model="s.price" type="number" min="0" step=".01" required></label>
      <label>可售库存<input v-model.number="s.available_stock" type="number" min="0" step="1" required></label>
      <button v-if="form.skus.length > 1" type="button" @click="form.skus.splice(i, 1)">
        移除规格
      </button>
    </fieldset>
    <button type="button" :disabled="form.skus.length >= 100" @click="form.skus.push(sku())">
      添加规格
    </button>
    <p v-if="error" role="alert">{{ error }}</p>
    <button :disabled="pending">保存草稿</button>
  </form>
</template>
