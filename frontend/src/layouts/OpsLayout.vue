<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()

onMounted(async () => {
  if (!userStore.profile) await userStore.restoreSession()
})
</script>

<template>
  <div class="ops-layout">
    <aside class="ops-layout__sidebar">
      <router-link class="ops-layout__brand" to="/ops" aria-label="SIQ运营工作台">
        <span class="ops-layout__brand-mark" aria-hidden="true">S</span>
        <span><strong>SIQ</strong><small>运营工作台</small></span>
      </router-link>

      <nav class="ops-layout__nav" aria-label="运营导航">
        <section class="ops-layout__group">
          <h2>总览</h2>
          <router-link to="/ops" exact-active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" /></svg>
            工作台
          </router-link>
        </section>
        <section v-if="userStore.profile?.can_manage_catalog" class="ops-layout__group">
          <h2>商品</h2>
          <router-link to="/ops/products" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 7 8-4 8 4-8 4zM4 7v10l8 4 8-4V7M12 11v10" /></svg>
            商品管理
          </router-link>
          <router-link to="/ops/categories" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16M4 12h16M4 19h16" /></svg>
            分类管理
          </router-link>
        </section>
        <section v-if="userStore.profile?.can_fulfill_orders || userStore.profile?.can_manage_promotions" class="ops-layout__group">
          <h2>交易与营销</h2>
          <router-link v-if="userStore.profile?.can_fulfill_orders" to="/ops/orders" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6" /></svg>
            订单履约
          </router-link>
          <router-link v-if="userStore.profile?.can_manage_promotions" to="/ops/coupons" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v5a2 2 0 0 0 0 4v5H4v-5a2 2 0 0 0 0-4zM12 7v2M12 12v2M12 17v1" /></svg>
            优惠券管理
          </router-link>
        </section>
        <section v-if="userStore.profile?.can_publish_content || userStore.profile?.can_moderate_reviews || userStore.profile?.can_reply_support || userStore.profile?.can_assign_support" class="ops-layout__group">
          <h2>内容与服务</h2>
          <router-link v-if="userStore.profile?.can_publish_content" to="/ops/cms" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h14v18H5zM8 8h8M8 12h8M8 16h5" /></svg>
            内容管理
          </router-link>
          <router-link v-if="userStore.profile?.can_publish_content" to="/ops/notification-templates" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>
            通知模板
          </router-link>
          <router-link v-if="userStore.profile?.can_moderate_reviews" to="/ops/reviews" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z" /></svg>
            评价审核
          </router-link>
          <router-link v-if="userStore.profile?.can_reply_support || userStore.profile?.can_assign_support" to="/ops/support" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15a3 3 0 0 1-3 3H9l-5 3v-6a3 3 0 0 1-1-2V7a3 3 0 0 1 3-3h11a3 3 0 0 1 3 3z" /></svg>
            客服工作台
          </router-link>
        </section>
        <section v-if="userStore.profile?.can_manage_roles || userStore.profile?.can_view_audit" class="ops-layout__group">
          <h2>系统</h2>
          <router-link v-if="userStore.profile?.can_manage_roles" to="/ops/access" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="4" /><path d="M2 21a7 7 0 0 1 14 0M17 8h5M19.5 5.5v5" /></svg>
            用户与角色
          </router-link>
          <router-link v-if="userStore.profile?.can_view_audit" to="/ops/audits" active-class="is-active">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6zM9 12l2 2 4-4" /></svg>
            运营审计
          </router-link>
        </section>
      </nav>
      <p class="ops-layout__note">仅展示当前账号权限内功能</p>
    </aside>

    <div class="ops-layout__workspace">
      <header class="ops-layout__header">
        <div>
          <p v-if="route.path === '/ops'">SIQ 优选商城 / 运营</p>
          <p v-else>运营工作台 / {{ route.meta.title }}</p>
          <h1 v-if="route.path === '/ops'">运营工作台</h1>
        </div>
        <nav aria-label="账户导航">
          <router-link to="/">返回商城</router-link>
          <router-link to="/account">我的账号</router-link>
        </nav>
      </header>
      <main class="ops-layout__main">
        <router-view :key="$route.path" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.ops-layout {
  --mall-control-height: 36px;
  display: grid;
  grid-template-columns: 224px minmax(0, 1fr);
  min-height: 100vh;
  color: #26332e;
  background: #f4f5f2;
}

.ops-layout__sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 24px 14px 18px;
  border-right: 1px solid #dfe4de;
  background: #fafaf7;
  overflow-y: auto;
}

.ops-layout__brand {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 44px;
  margin: 0 8px 26px;
  color: var(--mall-text);
  text-decoration: none;
}

.ops-layout__brand-mark {
  display: grid;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px 10px 10px 3px;
  color: #fff;
  background: var(--mall-color-primary);
  font-weight: 650;
}

.ops-layout__brand strong,
.ops-layout__brand small {
  display: block;
}

.ops-layout__brand strong {
  font-size: 16px;
  letter-spacing: 0.02em;
}

.ops-layout__brand small {
  margin-top: -2px;
  color: var(--mall-text-secondary);
  font-size: 11px;
  font-weight: 400;
}

.ops-layout__nav {
  display: grid;
  gap: 20px;
}

.ops-layout__group h2 {
  margin: 0 10px 6px;
  color: #78827c;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.ops-layout__group {
  display: grid;
  gap: 2px;
}

.ops-layout__group a {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 8px 10px;
  border-radius: 8px;
  color: #53615a;
  font-size: 13px;
  text-decoration: none;
  transition: color var(--mall-motion-fast) ease, background var(--mall-motion-fast) ease;
}

.ops-layout__group a:hover {
  color: var(--mall-color-primary);
  background: #f0f3ee;
}

.ops-layout__group a.is-active {
  color: var(--mall-color-primary);
  background: var(--mall-color-primary-light);
  font-weight: 600;
}

.ops-layout__group svg {
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.ops-layout__note {
  margin: auto 10px 0;
  padding-top: 24px;
  color: #78827c;
  font-size: 11px;
}

.ops-layout__workspace {
  min-width: 0;
}

.ops-layout__header {
  position: sticky;
  z-index: 20;
  top: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: 76px;
  padding: 12px 32px;
  border-bottom: 1px solid #dfe4de;
  background: rgb(244 245 242 / 92%);
  backdrop-filter: blur(16px);
}

.ops-layout__header p {
  margin: 0 0 1px;
  color: #78827c;
  font-size: 11px;
}

.ops-layout__header h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
  letter-spacing: -0.015em;
}

.ops-layout__header nav {
  display: flex;
  gap: 8px;
}

.ops-layout__header a {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 0 13px;
  border: 1px solid #d8ded7;
  border-radius: 8px;
  color: #53615a;
  background: #fff;
  font-size: 12px;
  text-decoration: none;
}

.ops-layout__header a:hover {
  color: var(--mall-color-primary);
  border-color: #b9c7bc;
}

.ops-layout__main {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}

.ops-layout__main :deep(.catalog) {
  max-width: none;
}

.ops-layout__main :deep(.ops-dashboard > h1) {
  display: none;
}

.ops-layout__main :deep(input),
.ops-layout__main :deep(select),
.ops-layout__main :deep(button) {
  min-height: var(--mall-control-height);
}

.ops-layout__main :deep(table) {
  font-size: 13px;
}

@media (pointer: coarse) {
  .ops-layout__group a,
  .ops-layout__header a,
  .ops-layout__main :deep(input),
  .ops-layout__main :deep(select),
  .ops-layout__main :deep(button) {
    min-height: 44px;
  }
}

@media (max-width: 900px) {
  .ops-layout {
    grid-template-columns: 1fr;
  }

  .ops-layout__sidebar {
    position: static;
    display: block;
    width: 100%;
    height: auto;
    padding: 12px 16px;
    border-right: 0;
    border-bottom: 1px solid #dfe4de;
    overflow: hidden;
  }

  .ops-layout__brand {
    margin: 0 0 10px;
  }

  .ops-layout__brand small,
  .ops-layout__note,
  .ops-layout__group h2 {
    display: none;
  }

  .ops-layout__nav {
    display: flex;
    gap: 12px;
    padding-bottom: 4px;
    overflow-x: auto;
  }

  .ops-layout__group {
    display: flex;
    flex-shrink: 0;
    gap: 4px;
  }

  .ops-layout__group a {
    white-space: nowrap;
  }

  .ops-layout__header {
    position: static;
    min-height: 68px;
    padding: 12px 20px;
  }

  .ops-layout__main {
    padding: 20px;
  }
}

@media (max-width: 600px) {
  .ops-layout__group svg {
    display: none;
  }

  .ops-layout__header {
    align-items: flex-start;
    padding: 12px 16px;
  }

  .ops-layout__header nav {
    gap: 4px;
  }

  .ops-layout__header a {
    padding: 0 9px;
  }

  .ops-layout__header a:last-child {
    display: none;
  }

  .ops-layout__main {
    padding: 16px 12px 32px;
  }
}
</style>
