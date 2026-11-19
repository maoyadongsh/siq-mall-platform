<script setup lang="ts">
import PublicReviews from '@/views/reviews/PublicReviews.vue'
import { computed, ref, watch } from 'vue'
import request from '@/utils/request'
import { messageOf, statusOf } from '@/utils/errors'
import { useUserStore } from '@/stores/user'
import { addGuest, addMember, pendingAdd } from '@/api/cart'
import type { Product, Sku } from '@/types/models'

const user = useUserStore()
const quantity = ref(1)
const busy = ref(false)
const notice = ref('')
const addError = ref('')
const props = defineProps({ id: { type: String, required: true } })
const product = ref<Product | null>(null)
const selected = ref<Sku | null>(null)
const error = ref('')
let generation = 0

const startingPrice = computed(() => {
  const skus = product.value?.skus
  if (!skus?.length) return null
  return skus.reduce((lowest, sku) => Number(sku.price) < Number(lowest.price) ? sku : lowest, skus[0]).price
})

function adjustQuantity(delta: number) {
  quantity.value = Math.min(99, Math.max(1, (quantity.value || 1) + delta))
}

async function add() {
  if (busy.value || !selected.value || !product.value) return
  busy.value = true
  notice.value = ''
  addError.value = ''
  try {
    await user.restoreSession()
    if (!Number.isInteger(quantity.value) || quantity.value < 1 || quantity.value > 99)
      throw new Error('数量须为1至99的整数')
    if (user.isLoggedIn) {
      const op = pendingAdd(user.profile!.id)
      if (op && (op.line.sku_id !== selected.value.id || op.line.quantity !== quantity.value))
        throw new Error('请先到购物车确认上次加购结果')
      await addMember(user.profile!.id, { sku_id: selected.value.id, quantity: quantity.value })
    } else addGuest(product.value, selected.value, quantity.value)
    notice.value = '已加入购物车'
  } catch (e) {
    addError.value = messageOf(e)
  } finally {
    busy.value = false
  }
}

async function load() {
  const ticket = ++generation
  product.value = null
  selected.value = null
  error.value = ''
  try {
    const data = await request.get<Product>('/products/' + props.id + '/')
    if (ticket === generation) product.value = data
  } catch (e) {
    if (ticket === generation)
      error.value = statusOf(e) === 404 ? '商品已下架或不存在' : messageOf(e)
  }
}
watch(() => props.id, load, { immediate: true })
</script>

<template>
  <section class="catalog product-detail">
    <router-link class="product-detail__back" to="/products"><span aria-hidden="true">←</span> 返回商品列表</router-link>
    <div v-if="error" role="alert" class="catalog__state catalog__state--error"><span>{{ error }}</span><button @click="load">重新加载</button></div>
    <div v-else-if="!product" class="catalog__state" role="status"><span class="catalog__spinner" aria-hidden="true" /><p>正在加载商品…</p></div>
    <template v-else>
      <article class="product-detail__layout" :class="{ 'product-detail__layout--no-media': !product.cover_url }">
        <div v-if="product.cover_url" class="product-detail__media">
          <img class="product-cover" :src="product.cover_url" :alt="product.title" width="960" height="720">
        </div>
        <div class="product-detail__info">
          <p class="catalog__eyebrow">{{ product.category }}</p>
          <h1>{{ product.title }}</h1>
          <p class="product-detail__description">{{ product.description }}</p>
          <div class="product-detail__assurance">
            <div><strong>实时核对</strong><span>库存与价格以提交时服务端结果为准</span></div>
            <div><strong>全程可查</strong><span>订单状态与站内消息集中保留</span></div>
          </div>
          <router-link class="product-detail__support" to="/support">需要帮助？联系客服 <span aria-hidden="true">↗</span></router-link>
        </div>

        <div class="product-detail__purchase">
          <fieldset>
            <legend>选择规格</legend>
            <div class="product-detail__sku-list">
              <button
                v-for="s in product.skus"
                :key="s.id"
                :aria-pressed="selected?.id === s.id"
                @click="selected = s"
              >
                <span>{{ s.label }}</span><small>{{ s.available_stock === 0 ? '暂时缺货' : `¥${s.price}` }}</small>
              </button>
            </div>
          </fieldset>

          <div class="product-detail__price" aria-live="polite">
            <p v-if="selected || startingPrice" class="siq-price"><span>¥</span>{{ selected?.price || startingPrice }}</p>
            <p v-else class="product-detail__select-tip">请选择规格查看价格</p>
            <small v-if="selected" :class="{ 'is-out': !selected.available_stock }">{{ selected.available_stock ? '当前规格有货' : '当前规格暂时缺货' }}</small>
            <small v-else>选择规格后确认价格与库存</small>
          </div>

          <div v-if="selected" class="product-detail__quantity">
            <span>购买数量</span>
            <div class="product-detail__stepper">
              <button :disabled="quantity <= 1" aria-label="减少数量" @click="adjustQuantity(-1)">−</button>
              <input v-model.number="quantity" aria-label="购买数量" type="number" min="1" max="99">
              <button :disabled="quantity >= 99" aria-label="增加数量" @click="adjustQuantity(1)">+</button>
            </div>
          </div>
          <p v-if="notice" role="status" class="product-detail__notice">{{ notice }} <router-link to="/cart">去购物车查看</router-link></p>
          <p v-if="addError" role="alert" class="product-detail__error">{{ addError }}</p>
        </div>

        <div class="product-detail__actionbar">
          <div><small>{{ selected ? '已选规格' : '当前起售价' }}</small><strong>{{ selected ? selected.label : `¥${startingPrice}` }}</strong></div>
          <router-link class="catalog-button catalog-button--secondary" to="/cart">购物车</router-link>
          <button class="catalog-button catalog-button--primary" :disabled="busy || !selected || !selected.available_stock" @click="add">{{ busy ? '正在加入…' : '加入购物车' }}</button>
        </div>
      </article>
      <PublicReviews :id="id" />
    </template>
  </section>
</template>
<style src="./catalog.css"></style>
