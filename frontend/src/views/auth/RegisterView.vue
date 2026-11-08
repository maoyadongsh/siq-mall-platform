<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElCard } from 'element-plus'
import 'element-plus/es/components/card/style/css'

import AuthForm from '@/components/auth/AuthForm.vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

async function submit(payload) {
  loading.value = true
  try {
    await userStore.register({
      username: payload.username,
      password: payload.password,
      accepted_terms_version: payload.accepted_terms_version,
    })
    await router.push('/account')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card class="auth-card" shadow="never">
    <template #header><h1>注册</h1></template>
    <AuthForm mode="register" :loading="loading" @submit="submit" />
    <p class="auth-card__hint">已有账号？<router-link to="/login">返回登录</router-link></p>
  </el-card>
</template>

<style scoped>
.auth-card {
  max-width: 460px;
  margin: 32px auto;
}
.auth-card h1 {
  margin: 0;
  font-size: 24px;
}
.auth-card__hint {
  margin-bottom: 0;
  text-align: center;
}
@media (max-width: 767px) {
  .auth-card {
    margin: 16px auto;
  }
}
</style>
