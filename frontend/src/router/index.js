import { createRouter, createWebHistory } from 'vue-router'

import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('@/views/home/Index.vue'),
          meta: { title: '首页' },
        },
        {
          path: 'login',
          name: 'login',
          component: () => import('@/views/auth/LoginView.vue'),
          meta: { title: '登录' },
        },
        {
          path: 'register',
          name: 'register',
          component: () => import('@/views/auth/RegisterView.vue'),
          meta: { title: '注册' },
        },
        {
          path: 'account/addresses',
          name: 'addresses',
          component: () => import('@/views/account/AddressView.vue'),
          meta: { title: '地址管理', requiresAuth: true },
        },
        {
          path: 'account',
          name: 'account',
          component: () => import('@/views/auth/AccountView.vue'),
          meta: { title: '我的账号', requiresAuth: true },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/error/NotFound.vue'),
      meta: { title: '页面不存在' },
    },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true
  const userStore = useUserStore()
  if (!userStore.isLoggedIn) await userStore.restoreSession()
  if (!userStore.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - SIQ优选商城` : 'SIQ优选商城'
})

export default router
