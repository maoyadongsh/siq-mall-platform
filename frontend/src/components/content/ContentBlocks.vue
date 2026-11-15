<script setup lang="ts">
import { computed } from 'vue'
import ProductGrid from './ProductGrid.vue'

interface GridProduct {
  id: string
  title: string
  cover_url?: string | null
  min_price?: string | null
}

interface HeadingBlock {
  type: 'heading'
  level: number | string
  text: string
}

interface TextBlock {
  type: 'text'
  text: string
}

interface RichTextBlock {
  type: 'rich_text'
  html: string
}

interface ImageBlock {
  type: 'image'
  url?: string
  alt?: string
  width?: number | string
  height?: number | string
}

interface LinkBlock {
  type: 'link'
  url: string
  label: string
}

interface ProductListBlock {
  type: 'product_list'
  products: GridProduct[]
}

interface UnknownBlock {
  type: 'unknown'
}

type ContentBlock =
  | HeadingBlock
  | TextBlock
  | RichTextBlock
  | ImageBlock
  | LinkBlock
  | ProductListBlock
  | UnknownBlock

const props = defineProps<{ blocks?: Record<string, unknown>[] }>()

function textOf(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

function optionalText(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}

function dimensionOf(value: unknown): number | string | undefined {
  return typeof value === 'number' || typeof value === 'string' ? value : undefined
}

function levelOf(value: unknown): number | string {
  return typeof value === 'number' || typeof value === 'string' ? value || 2 : 2
}

function productsOf(value: unknown): GridProduct[] {
  if (!Array.isArray(value)) return []
  return value.map((raw) => {
    const item = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
    return {
      id: textOf(item.id),
      title: textOf(item.title),
      cover_url: optionalText(item.cover_url) ?? null,
      min_price: item.min_price === null || item.min_price === undefined ? null : textOf(item.min_price),
    }
  })
}

function parseBlock(raw: Record<string, unknown>): ContentBlock {
  switch (raw.type) {
    case 'heading':
      return { type: 'heading', level: levelOf(raw.level), text: textOf(raw.text) }
    case 'text':
      return { type: 'text', text: textOf(raw.text) }
    case 'rich_text':
      return { type: 'rich_text', html: textOf(raw.html) }
    case 'image':
      return {
        type: 'image',
        url: optionalText(raw.url),
        alt: optionalText(raw.alt),
        width: dimensionOf(raw.width),
        height: dimensionOf(raw.height),
      }
    case 'link':
      return { type: 'link', url: textOf(raw.url), label: textOf(raw.label) }
    case 'product_list':
      return { type: 'product_list', products: productsOf(raw.products) }
    default:
      return { type: 'unknown' }
  }
}

const parsedBlocks = computed<ContentBlock[]>(() => (props.blocks ?? []).map(parseBlock))
</script>

<template>
  <div class="content-blocks">
    <template v-for="(block, index) in parsedBlocks" :key="index">
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
