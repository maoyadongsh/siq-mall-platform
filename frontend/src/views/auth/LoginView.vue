<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElCard } from 'element-plus'
import 'element-plus/es/components/card/style/css'

import AuthForm from '@/components/auth/AuthForm.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

async function submit(credentials) {
  loading.value = true
  try {
    await userStore.login({ identifier: credentials.identifier, password: credentials.password })
    const redirect = route.query.redirect
    const target =
      typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')
        ? redirect
        : '/account'
    await router.push(target)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card class="auth-card" shadow="never">
    <template #header><h1>登录</h1></template>
    <AuthForm mode="login" :loading="loading" @submit="submit" />
    <p class="auth-card__hint">
      还没有账号？<router-link
        :to="{ path: '/register', query: { redirect: route.query.redirect } }"
      >
        立即注册
      </router-link>
    </p>
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
