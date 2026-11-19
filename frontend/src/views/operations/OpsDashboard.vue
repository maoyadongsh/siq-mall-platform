<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getDashboard } from '@/api/operations'
import { messageOf } from '@/utils/errors'

interface DashboardTask {
  key: string
  path: string
  count: number
  label: string
}

const data = ref<Record<string, unknown> | null>(null)
const loading = ref(false)
const error = ref('')

const tasks = computed<DashboardTask[]>(() => {
  const raw = data.value?.tasks
  return Array.isArray(raw) ? (raw as DashboardTask[]) : []
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getDashboard()
  } catch (e) {
    error.value = messageOf(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="ops-dashboard">
    <header class="ops-dashboard__header"><div><p>YOUR WORK QUEUE</p><h2>从真实待办开始</h2><span>这里只显示当前账号权限内的工作，不展示虚构销售额或增长率。</span></div><button :disabled="loading" @click="load">{{ loading ? '正在更新…' : '刷新待办' }}</button></header>
    <div v-if="error" class="ops-dashboard__notice" role="alert"><span>{{ error }}</span><button @click="load">重试</button></div>
    <div v-if="loading && !data" class="ops-dashboard__loading" role="status">正在读取待办…</div>
    <div v-else-if="data" class="ops-dashboard__grid">
      <router-link v-for="task in tasks" :key="task.key" :to="task.path" class="ops-dashboard__card"><div><span>{{ task.label }}</span><strong>{{ task.count }}</strong></div><small>进入处理 <span aria-hidden="true">→</span></small></router-link>
      <div v-if="!tasks.length" class="ops-dashboard__empty"><span aria-hidden="true">S</span><h3>当前没有可见业务待办</h3><p>可以使用左侧权限内导航继续工作。</p></div>
    </div>
  </section>
</template>

<style scoped>
.ops-dashboard__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
  padding: 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  background: var(--mall-surface);
}
.ops-dashboard__header p {
  margin: 0 0 6px;
  color: var(--mall-text-secondary);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.13em;
}
.ops-dashboard__header h2 {
  margin: 0 0 6px;
  font-size: 21px;
  font-weight: 600;
}
.ops-dashboard__header span {
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.ops-dashboard button {
  min-height: 36px;
  padding: 6px 12px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-sm);
  color: var(--mall-color-primary);
  background: #fff;
  font-size: 12px;
}
.ops-dashboard__notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: var(--mall-radius-sm);
  color: var(--mall-color-danger);
  background: #fff3f1;
}
.ops-dashboard__loading {
  padding: 64px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  color: var(--mall-text-secondary);
  background: var(--mall-surface);
  text-align: center;
}
.ops-dashboard__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}
.ops-dashboard__card {
  display: grid;
  gap: 20px;
  padding: 20px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  color: var(--mall-color-primary);
  background: var(--mall-surface);
  text-decoration: none;
  transition: border-color var(--mall-motion-fast) ease, box-shadow var(--mall-motion-fast) ease;
}
.ops-dashboard__card:hover {
  border-color: var(--mall-border-strong);
  box-shadow: var(--mall-shadow-sm);
}
.ops-dashboard__card > div {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.ops-dashboard__card > div > span {
  padding-top: 5px;
  color: var(--mall-text);
  font-size: 13px;
  font-weight: 550;
}
.ops-dashboard__card strong {
  font-size: 30px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.ops-dashboard__card small {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--mall-border);
  color: var(--mall-text-secondary);
  font-size: 11px;
}
.ops-dashboard__empty {
  grid-column: 1 / -1;
  padding: 56px 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  background: var(--mall-surface);
  text-align: center;
}
.ops-dashboard__empty > span {
  display: grid;
  width: 40px;
  height: 40px;
  margin: 0 auto 14px;
  place-items: center;
  border-radius: 12px 12px 12px 4px;
  color: #fff;
  background: var(--mall-color-primary);
}
.ops-dashboard__empty h3 {
  margin-bottom: 8px;
  font-size: 17px;
}
.ops-dashboard__empty p {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
@media (pointer: coarse) {
  .ops-dashboard button {
    min-height: 44px;
  }
}
</style>
