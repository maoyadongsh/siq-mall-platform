<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { unreadNotifications } from '@/api/notifications'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const unread = ref(0)
let timer

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
  <div class="mall-layout">
    <header class="mall-layout__header">
      <div class="mall-layout__brand">SIQ优选商城</div>
      <nav class="mall-layout__nav">
        <router-link class="mall-layout__link" to="/">首页</router-link>
        <router-link class="mall-layout__link" to="/cart">购物车</router-link>
        <router-link class="mall-layout__link" to="/coupons">领券中心</router-link>
        <router-link
          v-if="userStore.profile?.can_manage_promotions"
          class="mall-layout__link"
          to="/ops/coupons"
        >
          优惠券管理
        </router-link>
        <router-link
          v-if="userStore.profile?.can_manage_catalog"
          class="mall-layout__link"
          to="/ops/products"
        >
          商品管理
        </router-link>
        <router-link
          v-if="userStore.profile?.can_fulfill_orders"
          class="mall-layout__link"
          to="/ops/orders"
        >
          订单履约
        </router-link>
        <router-link
          v-if="userStore.profile?.can_moderate_reviews"
          class="mall-layout__link"
          to="/ops/reviews"
        >
          评价审核
        </router-link>
        <router-link
          v-if="userStore.profile?.can_publish_content"
          class="mall-layout__link"
          to="/ops/cms"
        >
          内容管理
        </router-link>
        <router-link
          v-if="userStore.profile?.can_publish_content"
          class="mall-layout__link"
          to="/ops/notification-templates"
        >
          通知模板
        </router-link>
        <router-link v-if="userStore.isLoggedIn" class="mall-layout__link" to="/messages">
          消息<span v-if="unread" class="mall-layout__badge" :aria-label="unread + '条未读消息'">{{
            unread > 99 ? '99+' : unread
          }}</span>
        </router-link>
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
      <router-view :key="$route.path" />
    </main>

    <footer class="mall-layout__footer">SIQ优选商城</footer>
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
.mall-layout__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  min-height: 20px;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 10px;
  color: #fff;
  background: var(--mall-color-primary);
  font-size: 12px;
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
