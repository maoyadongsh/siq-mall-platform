<script setup>
import { onMounted, ref } from 'vue'
import { activateTemplate, listTemplates, reviseTemplate } from '@/api/notifications'
import './messages.css'

const rows = ref([])
const selected = ref(null)
const title = ref('')
const body = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listTemplates({ page_size: 100 })
    rows.value = data.results
    if (selected.value) {
      const current = rows.value.find((row) => row.id === selected.value.id)
      if (current) select(current)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function select(row) {
  selected.value = row
  title.value = row.title
  body.value = row.body
  error.value = ''
  notice.value = ''
}

async function save() {
  if (busy.value || !selected.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await reviseTemplate(selected.value, {
      title: title.value,
      body: body.value,
      variables: selected.value.supported_variables,
    })
    await load()
    select(result)
    notice.value = '已保存为新草稿版本；启用前线上模板不变。'
  } catch (e) {
    error.value = e.response?.data?.errors?.[0]?.detail || e.message
  } finally {
    busy.value = false
  }
}

async function activate() {
  if (busy.value || !selected.value) return
  const active = rows.value.find(
    (row) => row.event_type === selected.value.event_type && row.active,
  )
  if (!active) {
    error.value = '找不到当前启用版本，请刷新后重试。'
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await activateTemplate(selected.value, active.version)
    await load()
    select(result)
    notice.value = '新版本已启用，后续事件将使用此模板。'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="message-center">
    <div class="message-center__heading">
      <div>
        <h1>通知模板</h1>
        <p>仅支持登记的事件和变量；站内消息与微信订阅结果分别记录。</p>
      </div>
    </div>
    <p v-if="error" role="alert" class="message-center__error">{{ error }}</p>
    <p v-if="notice" role="status" class="message-center__success">{{ notice }}</p>
    <p v-if="loading">正在读取模板…</p>
    <div v-else class="template-layout">
      <div class="template-list">
        <button
          v-for="row in rows"
          :key="row.id"
          :class="{ selected: selected?.id === row.id }"
          @click="select(row)"
        >
          <strong>{{ row.event_type }} · v{{ row.version }}</strong>
          <span>{{ row.active ? '当前启用' : row.enabled ? '历史版本' : '未启用草稿' }}</span>
        </button>
      </div>
      <div v-if="selected" class="template-editor">
        <h2>编辑 {{ selected.event_type }}</h2>
        <p>
          允许变量：<code v-for="name in selected.supported_variables" :key="name">{{
            '{' + name + '}'
          }}</code><span v-if="!selected.supported_variables.length">无需变量</span>
        </p>
        <label>标题<input v-model="title" maxlength="100" required :disabled="busy"></label>
        <label>正文<textarea
          v-model="body"
          rows="5"
          maxlength="1000"
          required
          :disabled="busy"
        />
        </label>
        <div class="template-editor__actions">
          <button :disabled="busy || !title.trim() || !body.trim()" @click="save">
            保存为新版本
          </button>
          <button
            v-if="!selected.active"
            :disabled="busy || title !== selected.title || body !== selected.body"
            @click="activate"
          >
            启用此版本
          </button>
        </div>
        <section class="template-preview">
          <h3>服务端示例预览</h3>
          <strong>{{ selected.preview.title }}</strong>
          <p>{{ selected.preview.body }}</p>
        </section>
        <p class="template-editor__note">
          修改表单不会直接改变线上模板；先保存生成新版本，再核对预览并启用。微信订阅授权不代表已经送达，本项目未登记真实平台发送。
        </p>
      </div>
      <p v-else>请选择一个模板版本。</p>
    </div>
  </section>
</template>
