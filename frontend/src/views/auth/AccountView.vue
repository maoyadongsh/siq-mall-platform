<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElAlert,
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElInput,
} from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/card/style/css'
import 'element-plus/es/components/descriptions/style/css'
import 'element-plus/es/components/descriptions-item/style/css'
import 'element-plus/es/components/input/style/css'

import { logout, updateProfile } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const nickname = ref(userStore.profile?.nickname || '')
const profileMessage = ref('')
const profileError = ref('')

async function saveProfile() {
  saving.value = true
  profileMessage.value = ''
  profileError.value = ''
  try {
    const data = await updateProfile({ nickname: nickname.value })
    userStore.profile = data
    profileMessage.value = '昵称已保存'
  } catch (error) {
    profileError.value = error?.message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

async function signOut() {
  loading.value = true
  try {
    await logout()
  } finally {
    userStore.clear()
    localStorage.setItem('mall_session_logout_at', String(Date.now()))
    loading.value = false
    await router.push('/login')
  }
}
</script>

<template>
  <el-card class="account-card" shadow="never">
    <template #header><h1>我的账号</h1></template>
    <el-alert v-if="profileError" :title="profileError" type="error" :closable="false" show-icon />
    <el-alert
      v-if="profileMessage"
      :title="profileMessage"
      type="success"
      :closable="false"
      show-icon
    />
    <el-descriptions :column="1" border>
      <el-descriptions-item label="账号">{{ userStore.profile?.username }}</el-descriptions-item>
      <el-descriptions-item label="昵称">
        <div class="account-card__nickname">
          <el-input v-model="nickname" maxlength="50" />
          <el-button :loading="saving" @click="saveProfile">保存昵称</el-button>
        </div>
      </el-descriptions-item>
      <el-descriptions-item label="角色">
        {{ userStore.profile?.roles?.join('、') }}
      </el-descriptions-item>
    </el-descriptions>
    <div class="account-card__actions">
      <router-link class="account-card__address" to="/account/addresses">管理收货地址</router-link>
      <el-button class="account-card__logout" :loading="loading" @click="signOut">
        退出登录
      </el-button>
    </div>
  </el-card>
</template>

<style scoped>
.account-card {
  max-width: 640px;
  margin: 0 auto;
}
.account-card h1 {
  margin: 0;
  font-size: 24px;
}
.account-card__nickname {
  display: flex;
  align-items: center;
  gap: 8px;
}
.account-card__nickname .el-button {
  min-height: 44px;
}
.account-card__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 24px;
}
.account-card__address,
.account-card__logout {
  min-height: 44px;
}
.account-card__address {
  display: inline-flex;
  align-items: center;
}
:deep(.el-input__inner) {
  font-size: 16px;
}
</style>
