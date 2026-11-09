<script setup>
import { onMounted, ref } from 'vue'
import { getDashboard } from '@/api/operations'

const data = ref(null)
const loading = ref(false)
const error = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getDashboard()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="ops-dashboard">
    <h1>运营工作台</h1><p>这里只显示当前账号权限内的真实待办，不展示虚构销售额或增长率。</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="loading">正在读取待办…</p>
    <div v-else-if="data" class="ops-dashboard__grid">
      <router-link v-for="task in data.tasks" :key="task.key" :to="task.path" class="ops-dashboard__card"><strong>{{ task.count }}</strong><span>{{ task.label }}</span><small>进入处理</small></router-link>
      <p v-if="!data.tasks.length">当前没有可见业务待办；你可以使用上方权限内导航。</p>
    </div>
  </section>
</template>

<style scoped>
.ops-dashboard__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 24px;
}
.ops-dashboard__card {
  display: grid;
  gap: 10px;
  padding: 22px;
  border: 1px solid var(--mall-border);
  border-radius: 12px;
  color: var(--mall-color-primary);
  background: #fff;
  text-decoration: none;
}
.ops-dashboard__card strong {
  font-size: 32px;
}
.ops-dashboard__card small {
  color: var(--mall-text-secondary);
}
</style>
