<script setup>
import { ref, watch } from 'vue'
import request from '@/utils/request'
const props = defineProps({ id: { type: String, required: true } })
const product = ref(null),
  selected = ref(null),
  error = ref('')
let generation = 0
async function load() {
  const ticket = ++generation
  product.value = null
  selected.value = null
  error.value = ''
  try {
    const data = await request.get('/products/' + props.id + '/')
    if (ticket === generation) product.value = data
  } catch (e) {
    if (ticket === generation)
      error.value = e.response?.status === 404 ? '商品已下架或不存在' : e.message
  }
}
watch(() => props.id, load, { immediate: true })
</script>
<template>
  <section class="catalog">
    <router-link to="/">返回商品列表</router-link>
    <p v-if="error" role="alert">{{ error }} <button @click="load">重新加载</button></p>
    <p v-else-if="!product">正在加载商品…</p>
    <article v-else>
      <img
        v-if="product.cover_url"
        class="product-cover"
        :src="product.cover_url"
        :alt="product.title"
      >
      <small>{{ product.category }}</small>
      <h1>{{ product.title }}</h1>
      <p>{{ product.description }}</p>
      <fieldset>
        <legend>选择规格</legend>
        <button
          v-for="s in product.skus"
          :key="s.id"
          :aria-pressed="selected?.id === s.id"
          @click="selected = s"
        >
          {{ s.label }}{{ s.available_stock === 0 ? ' · 缺货' : '' }}
        </button>
      </fieldset>
      <p v-if="selected" aria-live="polite">
        ¥{{ selected.price }} · {{ selected.available_stock ? '有货' : '暂时缺货' }}
      </p>
    </article>
  </section>
</template>
<style src="./catalog.css"></style>
