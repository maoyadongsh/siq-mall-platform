<script setup>
import { ref, watch } from 'vue'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'
import { addGuest, addMember, pendingAdd } from '@/api/cart'
const user = useUserStore()
const quantity = ref(1),
  busy = ref(false),
  notice = ref(''),
  addError = ref('')
async function add() {
  if (busy.value || !selected.value) return
  busy.value = true
  notice.value = ''
  addError.value = ''
  try {
    await user.restoreSession()
    if (!Number.isInteger(quantity.value) || quantity.value < 1 || quantity.value > 99)
      throw new Error('数量须为1至99的整数')
    if (user.isLoggedIn) {
      const op = pendingAdd(user.profile.id)
      if (op && (op.line.sku_id !== selected.value.id || op.line.quantity !== quantity.value))
        throw new Error('请先到购物车确认上次加购结果')
      await addMember(user.profile.id, { sku_id: selected.value.id, quantity: quantity.value })
    } else addGuest(product.value, selected.value, quantity.value)
    notice.value = '已加入购物车'
  } catch (e) {
    addError.value = e.message
  } finally {
    busy.value = false
  }
}
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
      <div v-if="selected">
        <label>购买数量 <input v-model.number="quantity" type="number" min="1" max="99"></label>
        <button :disabled="busy || !selected.available_stock" @click="add">加入购物车</button>
        <router-link to="/cart">查看购物车</router-link>
        <p v-if="notice" role="status">{{ notice }}</p>
        <p v-if="addError" role="alert">{{ addError }}</p>
      </div>
    </article>
  </section>
</template>
<style src="./catalog.css"></style>
