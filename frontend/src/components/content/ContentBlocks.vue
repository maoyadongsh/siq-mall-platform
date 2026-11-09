<script setup>
import ProductGrid from './ProductGrid.vue'
defineProps({ blocks: { type: Array, default: () => [] } })
</script>

<template>
  <div class="content-blocks">
    <template v-for="(block, index) in blocks" :key="index">
      <component :is="`h${block.level || 2}`" v-if="block.type === 'heading'">{{ block.text }}</component>
      <p v-else-if="block.type === 'text'" class="content-blocks__text">{{ block.text }}</p>
      <!-- 唯一富文本入口：仅接收后端 nh3 白名单清洗与发布复核后的 HTML。 -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div v-else-if="block.type === 'rich_text'" class="content-blocks__rich" v-html="block.html" />
      <img
        v-else-if="block.type === 'image'"
        class="content-blocks__image"
        :src="block.url"
        :alt="block.alt"
        :width="block.width"
        :height="block.height"
        loading="lazy"
      >
      <p v-else-if="block.type === 'link'" class="content-blocks__link">
        <router-link v-if="block.url.startsWith('/')" :to="block.url">{{ block.label }}</router-link>
        <a v-else :href="block.url" target="_blank" rel="noopener noreferrer">{{ block.label }}</a>
      </p>
      <ProductGrid v-else-if="block.type === 'product_list'" :products="block.products || []" />
      <p v-else>此内容块暂不支持显示。</p>
    </template>
  </div>
</template>
