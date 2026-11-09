<script setup>
import { ref, onMounted } from 'vue'
import request from '@/utils/request'
import { couponAction, offer, stateName } from '@/api/coupons'
import TemplateForm from './TemplateForm.vue'
const data = ref(null),
  source = ref(null),
  editing = ref(false),
  busy = ref(false),
  error = ref(''),
  reason = ref(''),
  target = ref(null)
async function load(n = 1) {
  try {
    data.value = await request.get('/ops/coupons/', { params: { page: n } })
  } catch (e) {
    error.value = e.message
  }
}
function edit(c) {
  target.value = null
  source.value = c
  editing.value = true
}
function prepare(c) {
  editing.value = false
  target.value = c
  reason.value = ''
  error.value = ''
}
async function apply() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  const c = target.value
  try {
    await couponAction(c.id, c.status === 'draft' ? 'publish' : 'stop-claiming', {
      expected_version: c.version,
      reason: reason.value,
    })
    target.value = null
    await load(data.value.page)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function saved() {
  editing.value = false
  load()
}
onMounted(() => load())
</script>
<template>
  <section class="catalog">
    <header>
      <h1>优惠券管理</h1>
      <button @click="edit(null)">新建优惠券</button>
    </header>
    <TemplateForm
      v-if="editing"
      :key="source?.id || 'new'"
      :source="source"
      @saved="saved"
      @cancel="editing = false"
    />
    <p v-if="error" role="alert">{{ error }} <button @click="load()">刷新列表</button></p>
    <form v-if="target" class="draft" @submit.prevent="apply">
      <p>
        {{
          target.status === 'draft' ? '发布后将锁定经济条款' : '停领后，已领优惠券仍按原规则有效'
        }}：{{ target.name }}
      </p>
      <label>操作原因<input v-model.trim="reason" required maxlength="200"></label><button type="button" @click="target = null">返回</button><button :disabled="busy">确认{{ target.status === 'draft' ? '发布' : '停领' }}</button>
    </form>
    <p v-if="!data && !error">正在加载…</p>
    <template v-if="data">
      <p v-if="!data.results.length">暂无优惠券模板</p>
      <article v-for="c in data.results" :key="c.id">
        <small>{{ stateName[c.status] }}</small>
        <h2>{{ c.name }}</h2>
        <p>{{ offer(c) }}</p>
        <p>
          {{ c.scope === 'all' ? '全场商品' : '指定商品' }} · 限领 {{ c.per_user_limit }} · 有效至
          {{ new Date(c.end_at).toLocaleString() }}
        </p>
        <p>发行 {{ c.total }} · 已领 {{ c.issued }} · 占用 {{ c.reserved }} · 核销 {{ c.used }}</p>
        <button v-if="c.status === 'draft'" @click="edit(c)">编辑草稿</button><button v-if="c.status !== 'stopped'" @click="prepare(c)">
          {{ c.status === 'draft' ? '发布' : '停止领取' }}
        </button>
      </article>
      <nav v-if="data.total_pages > 1">
        <button :disabled="data.page === 1" @click="load(data.page - 1)">上一页</button>{{ data.page }} / {{ data.total_pages
        }}<button :disabled="data.page === data.total_pages" @click="load(data.page + 1)">
          下一页
        </button>
      </nav>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
