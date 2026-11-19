<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { unreadNotifications } from '@/api/notifications'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()
const unread = ref(0)
let timer: ReturnType<typeof setInterval> | undefined

const showMobileNav = computed(() => route.meta.mobileNav !== false)
const canOpenOps = computed(() => {
  const profile = userStore.profile
  return Boolean(
    profile?.can_manage_catalog ||
      profile?.can_fulfill_orders ||
      profile?.can_manage_promotions ||
      profile?.can_publish_content ||
      profile?.can_moderate_reviews ||
      profile?.can_reply_support ||
      profile?.can_assign_support ||
      profile?.can_manage_roles ||
      profile?.can_view_audit,
  )
})

async function refreshUnread() {
  if (!userStore.isLoggedIn) {
    unread.value = 0
    return
  }
  try {
    const data = await unreadNotifications()
    unread.value = data.total
  } catch {
    return
  }
}

function startPolling() {
  clearInterval(timer)
  refreshUnread()
  if (userStore.isLoggedIn) {
    timer = setInterval(() => {
      if (document.visibilityState === 'visible') refreshUnread()
    }, 60000)
  }
}

function visible() {
  if (document.visibilityState === 'visible') refreshUnread()
}

watch(() => userStore.isLoggedIn, startPolling)
onMounted(async () => {
  await userStore.restoreSession()
  startPolling()
  window.addEventListener('siq:notifications-changed', refreshUnread)
  document.addEventListener('visibilitychange', visible)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  window.removeEventListener('siq:notifications-changed', refreshUnread)
  document.removeEventListener('visibilitychange', visible)
})
</script>

<template>
  <div class="mall-layout" :class="{ 'mall-layout--with-tabbar': showMobileNav }">
    <header class="mall-layout__header">
      <div class="mall-layout__header-inner">
        <router-link class="mall-layout__brand" to="/" aria-label="SIQ优选商城首页">
          <span class="mall-layout__brand-mark" aria-hidden="true">S</span>
          <span class="mall-layout__brand-name">SIQ<span>优选商城</span></span>
        </router-link>

        <nav class="mall-layout__primary" aria-label="商城主导航">
          <router-link class="mall-layout__link" exact-active-class="is-active" to="/">首页</router-link>
          <router-link class="mall-layout__link" active-class="is-active" to="/products">选购</router-link>
          <router-link class="mall-layout__link" active-class="is-active" to="/coupons">领券中心</router-link>
        </nav>

        <nav class="mall-layout__utilities" aria-label="账户与服务">
          <router-link v-if="userStore.isLoggedIn" class="mall-layout__utility" to="/support">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15a3 3 0 0 1-3 3H9l-5 3v-6a3 3 0 0 1-1-2V7a3 3 0 0 1 3-3h11a3 3 0 0 1 3 3z" /></svg>
            <span class="mall-layout__utility-label">客服</span>
          </router-link>
          <router-link v-if="userStore.isLoggedIn" class="mall-layout__utility" to="/messages">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>
            <span class="mall-layout__utility-label">消息</span>
            <span v-if="unread" class="mall-layout__badge" :aria-label="unread + '条未读消息'">{{ unread > 99 ? '99+' : unread }}</span>
          </router-link>
          <router-link class="mall-layout__utility mall-layout__cart" to="/cart">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3h2l2.4 11.2a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 2-1.6L21 7H6M9 21h.01M18 21h.01" /></svg>
            <span class="mall-layout__utility-label">购物车</span>
          </router-link>
          <router-link v-if="canOpenOps" class="mall-layout__utility mall-layout__ops-link" to="/ops">运营工作台</router-link>
          <router-link v-if="userStore.isLoggedIn" class="mall-layout__account" to="/account">我的账号</router-link>
          <template v-else>
            <router-link class="mall-layout__login" to="/login">登录</router-link>
            <router-link class="mall-layout__register" to="/register">注册</router-link>
          </template>
        </nav>
      </div>
    </header>

    <main class="mall-layout__main">
      <router-view :key="$route.path" />
    </main>

    <footer class="mall-layout__footer">
      <div class="mall-layout__footer-inner">
        <div>
          <router-link class="mall-layout__footer-brand" to="/">SIQ优选商城</router-link>
          <p>认真选好每一件日常用品。</p>
        </div>
        <div class="mall-layout__footer-meta">
          <p>真实商品 · 清晰价格 · 可查询订单</p>
          <small>演示商城，支付仅为模拟</small>
        </div>
      </div>
    </footer>

    <nav v-if="showMobileNav" class="mall-tabbar" aria-label="移动端主导航">
      <router-link to="/" exact-active-class="is-active">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 9-8 9 8v9a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z" /></svg>
        <span>首页</span>
      </router-link>
      <router-link to="/products" active-class="is-active">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM4 10h16M10 10v9" /></svg>
        <span>选购</span>
      </router-link>
      <router-link to="/cart" active-class="is-active">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3h2l2.4 11.2a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 2-1.6L21 7H6M9 21h.01M18 21h.01" /></svg>
        <span>购物车</span>
      </router-link>
      <router-link :to="userStore.isLoggedIn ? '/account' : '/login'" active-class="is-active">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
        <span>我的</span>
      </router-link>
    </nav>
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
  position: sticky;
  z-index: var(--mall-z-header);
  top: 0;
  border-bottom: 1px solid rgb(23 76 67 / 8%);
  background: rgb(247 246 242 / 88%);
  backdrop-filter: saturate(160%) blur(18px);
}

.mall-layout__header-inner {
  display: flex;
  align-items: center;
  gap: 32px;
  width: min(100% - 48px, 1320px);
  min-height: var(--mall-header-height);
  margin: 0 auto;
}

.mall-layout__brand {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 11px;
  min-height: 44px;
  color: var(--mall-text);
  text-decoration: none;
}

.mall-layout__brand-mark {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 10px 10px 10px 3px;
  color: #fff;
  background: var(--mall-color-primary);
  font-size: 17px;
  font-weight: 650;
  letter-spacing: -0.04em;
}

.mall-layout__brand-name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.mall-layout__brand-name span {
  margin-left: 7px;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0;
}

.mall-layout__primary,
.mall-layout__utilities {
  display: flex;
  align-items: center;
}

.mall-layout__primary {
  gap: 4px;
}

.mall-layout__link,
.mall-layout__utility,
.mall-layout__account,
.mall-layout__login {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  color: var(--mall-text-secondary);
  text-decoration: none;
  transition: color var(--mall-motion-fast) ease, background var(--mall-motion-fast) ease;
}

.mall-layout__link {
  padding: 0 15px;
  border-radius: var(--mall-radius-pill);
  font-size: 14px;
}

.mall-layout__link:hover,
.mall-layout__link.is-active {
  color: var(--mall-color-primary);
  background: rgb(23 76 67 / 6%);
}

.mall-layout__utilities {
  gap: 4px;
  margin-left: auto;
}

.mall-layout__utility {
  gap: 6px;
  padding: 0 10px;
  border-radius: var(--mall-radius-pill);
  font-size: 13px;
}

.mall-layout__utility svg,
.mall-tabbar svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.mall-layout__utility:hover,
.mall-layout__utility.router-link-active,
.mall-layout__login:hover {
  color: var(--mall-color-primary);
}

.mall-layout__ops-link {
  margin-left: 4px;
  color: var(--mall-color-primary);
  background: var(--mall-color-primary-light);
}

.mall-layout__account {
  margin-left: 6px;
  padding: 0 15px;
  border-radius: var(--mall-radius-pill);
  color: #fff;
  background: var(--mall-color-primary);
  font-size: 13px;
}

.mall-layout__account:hover,
.mall-layout__register:hover {
  background: var(--mall-color-primary-hover);
}

.mall-layout__login {
  padding: 0 10px;
  font-size: 14px;
}

.mall-layout__register {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  padding: 0 16px;
  border-radius: var(--mall-radius-pill);
  color: #fff;
  background: var(--mall-color-primary);
  font-size: 13px;
  text-decoration: none;
  transition: background var(--mall-motion-fast) ease;
}

.mall-layout__badge {
  position: absolute;
  top: 1px;
  right: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  min-height: 18px;
  padding: 0 5px;
  border: 2px solid var(--mall-bg);
  border-radius: var(--mall-radius-pill);
  color: #fff;
  background: var(--mall-color-accent);
  font-size: 10px;
  line-height: 1;
}

.mall-layout__main {
  flex: 1;
  width: 100%;
  padding: 40px 32px 64px;
}

.mall-layout__footer {
  padding: 0 32px;
  border-top: 1px solid var(--mall-border);
  background: var(--mall-surface-subtle);
}

.mall-layout__footer-inner {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  width: min(100%, var(--mall-content-width));
  margin: 0 auto;
  padding: 40px 0;
}

.mall-layout__footer-brand {
  color: var(--mall-color-primary);
  font-size: 16px;
  font-weight: 650;
  text-decoration: none;
}

.mall-layout__footer p {
  margin: 8px 0 0;
  color: var(--mall-text-secondary);
  font-size: 13px;
}

.mall-layout__footer-meta {
  text-align: right;
}

.mall-layout__footer small {
  display: block;
  margin-top: 5px;
  color: var(--mall-text-secondary);
  font-size: 12px;
}

.mall-tabbar {
  display: none;
}

@media (max-width: 1100px) {
  .mall-layout__header-inner {
    gap: 16px;
  }

  .mall-layout__utility-label,
  .mall-layout__brand-name span {
    display: none;
  }

  .mall-layout__utility {
    width: 42px;
    padding: 0;
  }

  .mall-layout__ops-link {
    width: auto;
    padding: 0 12px;
  }
}

@media (max-width: 767px) {
  .mall-layout__header-inner {
    width: calc(100% - 32px);
    min-height: 60px;
  }

  .mall-layout__brand-mark {
    width: 30px;
    height: 30px;
  }

  .mall-layout__primary,
  .mall-layout__cart,
  .mall-layout__account,
  .mall-layout__login,
  .mall-layout__register {
    display: none;
  }

  .mall-layout__utilities {
    gap: 2px;
  }

  .mall-layout__main {
    padding: 24px 16px 48px;
  }

  .mall-layout--with-tabbar .mall-layout__main {
    padding-bottom: 32px;
  }

  .mall-layout__footer {
    padding: 0 20px;
  }

  .mall-layout--with-tabbar .mall-layout__footer {
    padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px));
  }

  .mall-layout__footer-inner {
    align-items: flex-start;
    padding: 28px 0;
  }

  .mall-layout__footer-meta {
    display: none;
  }

  .mall-tabbar {
    position: fixed;
    z-index: var(--mall-z-navigation);
    right: 0;
    bottom: 0;
    left: 0;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    padding: 6px max(8px, env(safe-area-inset-right, 0px)) max(6px, env(safe-area-inset-bottom, 0px)) max(8px, env(safe-area-inset-left, 0px));
    border-top: 1px solid rgb(23 76 67 / 10%);
    background: rgb(250 249 246 / 94%);
    backdrop-filter: saturate(160%) blur(18px);
  }

  .mall-tabbar a {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-height: 54px;
    border-radius: var(--mall-radius-md);
    color: var(--mall-text-secondary);
    font-size: 11px;
    line-height: 1.3;
    text-decoration: none;
  }

  .mall-tabbar a.is-active {
    color: var(--mall-color-primary);
    font-weight: 600;
  }

  .mall-tabbar svg {
    width: 23px;
    height: 23px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .mall-layout__header,
  .mall-tabbar {
    backdrop-filter: none;
  }
}
</style>
