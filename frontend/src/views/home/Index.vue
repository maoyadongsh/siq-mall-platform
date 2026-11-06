<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ElAlert,
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/card/style/css'
import 'element-plus/es/components/descriptions/style/css'
import 'element-plus/es/components/descriptions-item/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/table-column/style/css'
import 'element-plus/es/components/tag/style/css'

import { fetchHealth } from '@/api/health'

const loading = ref(false)
const health = ref(null)
const errorMessage = ref('')
const isNarrow = ref(false)
let narrowMediaQuery

const statusText = computed(() => {
  if (errorMessage.value) return '不可用'
  if (!health.value) return '检测中'
  return health.value.status === 'ok' ? '正常' : '降级'
})

const statusType = computed(() => {
  if (errorMessage.value) return 'danger'
  if (!health.value) return 'info'
  return health.value.status === 'ok' ? 'success' : 'warning'
})

const checks = computed(() => {
  const raw = health.value?.checks || {}
  return Object.entries(raw).map(([name, detail]) => ({
    name: name === 'database' ? '数据库 MariaDB' : '缓存 Redis',
    status: detail.status,
    latency: detail.latency_ms,
    detail: detail.detail,
  }))
})

function handleViewportChange(event) {
  isNarrow.value = event.matches
}

async function loadHealth() {
  loading.value = true
  errorMessage.value = ''
  try {
    health.value = await fetchHealth()
  } catch (error) {
    health.value = null
    errorMessage.value = error?.message || '无法连接后端服务'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  narrowMediaQuery = window.matchMedia('(max-width: 767px)')
  isNarrow.value = narrowMediaQuery.matches
  narrowMediaQuery.addEventListener('change', handleViewportChange)
  loadHealth()
})

onBeforeUnmount(() => {
  narrowMediaQuery?.removeEventListener('change', handleViewportChange)
})
</script>

<template>
  <div class="home">
    <el-card shadow="never" class="home__card">
      <template #header>
        <div class="home__header">
          <span class="home__title">服务状态</span>
          <el-button :loading="loading" size="small" @click="loadHealth">重新检测</el-button>
        </div>
      </template>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="home__alert"
      />

      <el-descriptions v-else :column="isNarrow ? 1 : 2" border>
        <el-descriptions-item label="整体状态">
          <el-tag :type="statusType">{{ statusText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="服务">{{ health?.service || '-' }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ health?.version || '-' }}</el-descriptions-item>
        <el-descriptions-item label="环境">{{ health?.environment || '-' }}</el-descriptions-item>
        <el-descriptions-item label="服务端时间">
          {{ health?.server_time || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-table
        v-if="checks.length"
        :data="checks"
        :class="['home__table', { 'home__table--narrow': isNarrow }]"
        size="small"
      >
        <el-table-column prop="name" label="依赖" :width="isNarrow ? 112 : 160" />
        <el-table-column label="状态" :width="isNarrow ? 64 : 100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ok' ? 'success' : 'danger'" size="small">
              {{ row.status === 'ok' ? '正常' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="latency" label="耗时(ms)" :width="isNarrow ? 72 : 100" />
        <el-table-column prop="detail" label="详情" min-width="120" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.home__card {
  max-width: 960px;
  margin: 0 auto;
}

.home__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.home__title {
  font-weight: 600;
}

.home__alert {
  margin-bottom: var(--mall-spacing-md);
}

.home__table {
  margin-top: var(--mall-spacing-md);
}

.home__table--narrow :deep(.cell) {
  padding: 0 6px;
}

@media (max-width: 767px) {
  .home__header :deep(.el-button) {
    min-height: 44px;
  }
}
</style>
