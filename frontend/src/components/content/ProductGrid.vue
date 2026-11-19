<script setup lang="ts">
import { reactive } from 'vue'

interface GridProduct {
  id: string
  title: string
  category?: string
  cover_url?: string | null
  min_price?: string | null
  skus?: { price: string }[]
}

defineProps<{ products: GridProduct[] }>()
const failedImages = reactive(new Set<string>())

function startingPrice(product: GridProduct) {
  if (product.min_price != null) return product.min_price
  if (!product.skus?.length) return null
  return product.skus.reduce((lowest, sku) => Number(sku.price) < Number(lowest.price) ? sku : lowest, product.skus[0]).price
}
</script>

<template>
  <div class="product-grid">
    <article v-for="product in products" :key="product.id" class="product-card">
      <router-link class="product-card__link" :to="`/products/${product.id}`" :aria-label="`查看${product.title}规格`">
        <img
          v-if="product.cover_url && !failedImages.has(product.id)"
          class="product-cover"
          :src="product.cover_url"
          :alt="product.title"
          width="800"
          height="600"
          loading="lazy"
          @error="failedImages.add(product.id)"
        >
        <div class="product-card__body">
          <p v-if="product.category" class="product-card__category">{{ product.category }}</p>
          <h3>{{ product.title }}</h3>
          <div class="product-card__footer">
            <p v-if="startingPrice(product) != null" class="product-card__price"><span>¥</span>{{ startingPrice(product) }} <small>起</small></p>
            <span class="product-card__action">查看规格 <span aria-hidden="true">↗</span></span>
          </div>
        </div>
      </router-link>
    </article>
  </div>
</template>

<style scoped>
.product-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 32px 20px;
}
.product-card {
  min-width: 0;
}
.product-card__link {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-radius: var(--mall-radius-md);
  color: var(--mall-text);
  text-decoration: none;
}
.product-cover {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: var(--mall-radius-md);
  object-fit: cover;
  background: var(--mall-surface-subtle);
  transition: transform var(--mall-motion-slow) ease;
}
.product-card__link:hover .product-cover {
  transform: scale(1.015);
}
.product-card__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  padding: 15px 2px 0;
}
.product-card__category {
  margin: 0 0 5px;
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.product-card h3 {
  min-height: 2.8em;
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 550;
  line-height: 1.45;
  letter-spacing: -0.01em;
}
.product-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
}
.product-card__price {
  margin: 0;
  color: var(--mall-color-primary);
  font-size: 17px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.product-card__price > span {
  margin-right: 2px;
  font-size: 12px;
}
.product-card__price small {
  color: var(--mall-text-secondary);
  font-size: 11px;
  font-weight: 400;
}
.product-card__action {
  flex-shrink: 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
  transition: color var(--mall-motion-fast) ease;
}
.product-card__link:hover .product-card__action {
  color: var(--mall-color-primary);
}
.product-card__link:focus-visible {
  outline-offset: 5px;
}
@media (max-width: 1199px) {
  .product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 767px) {
  .product-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 28px;
  }
  .product-card h3 {
    min-height: 0;
    font-size: 16px;
  }
}
</style>
