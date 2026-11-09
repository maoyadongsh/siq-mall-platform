<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  cmsKinds,
  getContent,
  previewContent,
  publicationStates,
  publishContent,
  saveDraft,
  uploadMedia,
} from '@/api/cms'
import ContentBlocks from '@/components/content/ContentBlocks.vue'
import './content.css'

const props = defineProps({ id: { type: String, required: true } })
const content = ref(null)
const meta = ref({})
const blocks = ref([])
const selected = ref(0)
const previewData = ref(null)
const previewRevision = ref(1)
const platform = ref('web')
const original = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const reason = ref('')
const currentBlock = computed(() => blocks.value[selected.value])
const dirty = computed(() => content.value && snapshot() !== original.value)
const blockLabels = { heading: '标题', text: '正文', rich_text: '受限富文本', image: '图片', link: '链接', product_list: '商品推荐' }

function inputTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
function snapshot() {
  return JSON.stringify({ meta: meta.value, blocks: blocks.value })
}
function apply(row) {
  content.value = row
  const revision = row.latest_revision
  meta.value = {
    title: revision.title,
    slug: row.slug,
    start_at: inputTime(revision.start_at),
    end_at: inputTime(revision.end_at),
    sort_order: revision.sort_order,
    notify_inbox: revision.notify_inbox,
    platforms: [...revision.platforms],
  }
  blocks.value = JSON.parse(JSON.stringify(revision.blocks))
  selected.value = Math.min(selected.value, Math.max(0, blocks.value.length - 1))
  previewRevision.value = revision.revision_no
  original.value = snapshot()
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    apply(await getContent(props.id))
    await loadPreview()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function loadPreview() {
  if (!content.value) return
  previewData.value = await previewContent(props.id, previewRevision.value, platform.value)
}
function add(type) {
  const defaults = {
    heading: { type, text: '新标题', level: 2 },
    text: { type, text: '新正文' },
    rich_text: { type, html: '<p>新内容</p>' },
    image: { type, asset_id: null, mobile_asset_id: null, alt: '内容图片' },
    link: { type, label: '查看详情', url: '/' },
    product_list: { type, product_ids: [] },
  }
  blocks.value.push(defaults[type])
  selected.value = blocks.value.length - 1
}
function move(delta) {
  const target = selected.value + delta
  if (target < 0 || target >= blocks.value.length) return
  const [block] = blocks.value.splice(selected.value, 1)
  blocks.value.splice(target, 0, block)
  selected.value = target
}
function setProductIds(value) {
  currentBlock.value.product_ids = value.split(/[，,\s]+/).filter(Boolean).map(Number)
}
async function upload(event, mobile = false) {
  const file = event.target.files?.[0]
  if (!file) return
  busy.value = true
  error.value = ''
  try {
    const asset = await uploadMedia(file)
    currentBlock.value[mobile ? 'mobile_asset_id' : 'asset_id'] = Number(asset.asset_id)
    notice.value = '图片已完成内容校验并上传，保存草稿后生效。'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
    event.target.value = ''
  }
}
async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const row = await saveDraft(props.id, {
      expected_version: content.value.version,
      slug: content.value.slug,
      ...meta.value,
      start_at: new Date(meta.value.start_at).toISOString(),
      end_at: meta.value.end_at ? new Date(meta.value.end_at).toISOString() : null,
      blocks: blocks.value,
    })
    apply(row)
    await loadPreview()
    notice.value = '草稿已保存为新版本，线上内容未改变。'
  } catch (e) {
    error.value = e.response?.data?.errors?.[0]?.detail || e.message
  } finally {
    busy.value = false
  }
}
async function publish(action) {
  if (busy.value || dirty.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const row = await publishContent(content.value, action, reason.value)
    apply(row)
    await loadPreview()
    notice.value = action === 'publish' ? '版本已发布，首页缓存已失效。' : '内容已下线，公开入口不再返回。'
    reason.value = ''
  } catch (e) {
    error.value = e.response ? e.message : `${e.message}；结果待确认，请使用原提交标识重试或刷新核对。`
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="cms-editor">
    <div class="cms-ops__heading"><div><router-link to="/ops/cms">返回内容管理</router-link><h1>{{ content?.latest_revision.title || '内容编辑' }}</h1><p v-if="content">{{ cmsKinds[content.kind] }} · {{ publicationStates[content.publication_state] }} · 编辑版本 {{ content.version }}</p></div></div>
    <p v-if="error" role="alert" class="cms-error">{{ error }}</p><p v-if="notice" role="status" class="cms-success">{{ notice }}</p>
    <p v-if="loading">正在读取内容…</p>
    <div v-else-if="content" class="cms-editor__grid">
      <aside class="cms-block-panel">
        <h2>内容块</h2>
        <div class="cms-block-palette"><button v-for="(label, type) in blockLabels" :key="type" :disabled="busy" @click="add(type)">+ {{ label }}</button></div>
        <ol><li v-for="(block, index) in blocks" :key="index"><button :aria-pressed="selected === index" @click="selected = index">{{ index + 1 }}. {{ blockLabels[block.type] }}</button><span><button :disabled="index === 0" aria-label="上移内容块" @click="selected = index; move(-1)">↑</button><button :disabled="index === blocks.length - 1" aria-label="下移内容块" @click="selected = index; move(1)">↓</button><button aria-label="删除内容块" @click="blocks.splice(index, 1); selected = 0">删</button></span></li></ol>
        <form v-if="currentBlock" class="cms-block-fields" @submit.prevent>
          <h3>编辑{{ blockLabels[currentBlock.type] }}</h3>
          <template v-if="currentBlock.type === 'heading'"><label>标题文字<input v-model="currentBlock.text" maxlength="120"></label><label>层级<select v-model.number="currentBlock.level"><option :value="1">H1</option><option :value="2">H2</option><option :value="3">H3</option></select></label></template>
          <label v-else-if="currentBlock.type === 'text'">正文<textarea v-model="currentBlock.text" rows="6" maxlength="5000" /></label>
          <label v-else-if="currentBlock.type === 'rich_text'">受限HTML<textarea v-model="currentBlock.html" rows="8" /></label>
          <template v-else-if="currentBlock.type === 'image'"><label>替代文本<input v-model="currentBlock.alt" maxlength="120"></label><label>主图上传<input type="file" accept="image/png,image/jpeg,image/webp" @change="upload($event)"></label><p>媒体ID：{{ currentBlock.asset_id || '未上传' }}</p><label>移动裁切图（可选）<input type="file" accept="image/png,image/jpeg,image/webp" @change="upload($event, true)"></label><p>移动媒体ID：{{ currentBlock.mobile_asset_id || '与主图相同' }}</p></template>
          <template v-else-if="currentBlock.type === 'link'"><label>链接文字<input v-model="currentBlock.label" maxlength="80"></label><label>链接地址<input v-model="currentBlock.url" placeholder="/products/1 或 https://…"></label></template>
          <label v-else-if="currentBlock.type === 'product_list'">推荐商品ID<input :value="currentBlock.product_ids.join(',')" placeholder="1,2,3" @input="setProductIds($event.target.value)"></label>
        </form>
      </aside>
      <section class="cms-preview-panel">
        <div class="cms-preview-panel__heading"><h2>授权预览</h2><label>展示端<select v-model="platform" @change="loadPreview"><option value="web">PC / Web</option><option value="mobile">移动H5</option><option value="mini">小程序结构</option></select></label></div>
        <label>预览版本<select v-model.number="previewRevision" @change="loadPreview"><option v-for="revision in content.revisions" :key="revision.revision_no" :value="revision.revision_no">v{{ revision.revision_no }}</option></select></label>
        <p v-if="dirty" class="cms-preview-panel__dirty">有未保存修改；为避免展示未清洗内容，请先保存再预览或发布。</p>
        <div v-if="previewData" class="cms-preview-panel__canvas"><ContentBlocks :blocks="previewData.revision.blocks" /></div>
      </section>
      <aside class="cms-config-panel">
        <h2>发布配置</h2>
        <label>内容标题<input v-model="meta.title" maxlength="120" required></label>
        <label>内容标识<input v-model="meta.slug" disabled></label>
        <label>开始时间<input v-model="meta.start_at" type="datetime-local" required></label>
        <label>结束时间<input v-model="meta.end_at" type="datetime-local"></label>
        <label>排序<input v-model.number="meta.sort_order" type="number"></label>
        <fieldset><legend>展示端</legend><label v-for="item in [['web','PC'],['mobile','移动H5'],['mini','小程序']]" :key="item[0]"><input v-model="meta.platforms" type="checkbox" :value="item[0]"> {{ item[1] }}</label></fieldset>
        <label v-if="content.kind === 'announcement'"><input v-model="meta.notify_inbox" type="checkbox"> 发布此公告版本时发送站内通知</label>
        <button :disabled="busy || !blocks.length || !meta.platforms.length || !meta.title || !meta.start_at" @click="save">保存草稿</button>
        <label>操作原因<textarea v-model="reason" maxlength="200" :placeholder="content.status === 'published' ? '下线必填' : '发布说明'" /></label>
        <button :disabled="busy || dirty" @click="publish('publish')">发布内容</button>
        <button v-if="content.status === 'published'" :disabled="busy || dirty || !reason.trim()" @click="publish('unpublish')">下线内容</button>
        <p class="cms-config-panel__note">保存只新增草稿版本。发布时再次校验商品、媒体、内容块和链接；下线立即使公开入口失效。</p>
      </aside>
    </div>
  </section>
</template>
