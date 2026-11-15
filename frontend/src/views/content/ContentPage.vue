<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { getPublicContent } from '@/api/cms'
import { messageOf, statusOf } from '@/utils/errors'
import type { PublicContent } from '@/types/models'
import ContentBlocks from '@/components/content/ContentBlocks.vue'
import './content.css'

const props = defineProps({ kind: { type: String, required: true }, identifier: { type: String, required: true } })
const data = ref<PublicContent | null>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  data.value = null
  try {
    data.value = await getPublicContent(props.kind, props.identifier, window.innerWidth < 768 ? 'mobile' : 'web')
  } catch (e) {
    error.value = statusOf(e) === 404 ? '内容不存在、尚未发布或已下线。' : messageOf(e)
  } finally {
    loading.value = false
  }
}
watch(() => [props.kind, props.identifier], load)
onMounted(load)
</script>

<template>
  <article class="cms-page">
    <p v-if="loading" class="cms-loading">正在读取内容…</p>
    <div v-else-if="error" class="cms-empty"><p role="alert">{{ error }}</p><button @click="load">重新加载</button><router-link to="/">返回首页</router-link></div>
    <template v-else-if="data">
      <h1>{{ data.revision.title }}</h1>
      <ContentBlocks :blocks="data.revision.blocks" />
    </template>
  </article>
</template>
