<script setup>
defineProps({ products: { type: Array, default: () => [] } })
</script>

<template>
  <div class="product-grid">
    <article v-for="product in products" :key="product.id" class="product-card">
      <img v-if="product.cover_url" class="product-cover" :src="product.cover_url" :alt="product.title" loading="lazy">
      <div class="product-card__body">
        <h3>{{ product.title }}</h3>
        <p v-if="product.min_price !== null">¥{{ product.min_price }} 起</p>
        <router-link :to="`/products/${product.id}`">查看规格</router-link>
      </div>
    </article>
  </div>
</template>
