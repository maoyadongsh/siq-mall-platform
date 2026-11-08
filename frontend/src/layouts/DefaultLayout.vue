<script setup>
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
onMounted(() => userStore.restoreSession())
</script>

<template>
  <div class="mall-layout">
    <header class="mall-layout__header">
      <div class="mall-layout__brand">SIQ优选商城</div>
      <nav class="mall-layout__nav">
        <router-link class="mall-layout__link" to="/">首页</router-link>
        <router-link v-if="userStore.isLoggedIn" class="mall-layout__link" to="/account">
          我的账号
        </router-link>
        <template v-else>
          <router-link class="mall-layout__link" to="/login">登录</router-link>
          <router-link class="mall-layout__link" to="/register">注册</router-link>
        </template>
      </nav>
    </header>

    <main class="mall-layout__main">
      <router-view />
    </main>

    <footer class="mall-layout__footer">SIQ优选商城 · 身份与权限</footer>
  </div>
</template>

<style scoped>
.mall-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--mall-bg);
}
.mall-layout__header {
  display: flex;
  align-items: center;
  gap: var(--mall-spacing-lg);
  min-height: 60px;
  padding: 0 var(--mall-spacing-xl);
  background: #fff;
  border-bottom: 1px solid var(--mall-border);
}
.mall-layout__brand {
  flex-shrink: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--mall-color-primary);
}
.mall-layout__nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--mall-spacing-md);
}
.mall-layout__link {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: var(--mall-text);
  text-decoration: none;
}
.mall-layout__link:hover {
  color: var(--mall-color-primary);
}
.mall-layout__main {
  flex: 1;
  padding: var(--mall-spacing-xl);
}
.mall-layout__footer {
  padding: var(--mall-spacing-md) var(--mall-spacing-xl);
  text-align: center;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
@media (max-width: 767px) {
  .mall-layout__header {
    gap: var(--mall-spacing-md);
    padding-right: max(var(--mall-spacing-md), env(safe-area-inset-right, 0px));
    padding-left: max(var(--mall-spacing-md), env(safe-area-inset-left, 0px));
  }
  .mall-layout__nav {
    gap: 12px;
  }
  .mall-layout__main {
    padding: var(--mall-spacing-md);
  }
  .mall-layout__footer {
    padding: var(--mall-spacing-md);
    padding-bottom: max(var(--mall-spacing-md), env(safe-area-inset-bottom, 0px));
  }
}
</style>
