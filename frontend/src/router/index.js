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
          path: 'coupons',
          component: () => import('@/views/coupons/Coupons.vue'),
          meta: { title: '领券中心' },
        },
        {
          path: 'account/coupons',
          component: () => import('@/views/coupons/Coupons.vue'),
          props: { wallet: true },
          meta: { title: '我的优惠券', requiresAuth: true },
        },
        {
          path: 'ops/coupons',
          component: () => import('@/views/coupons/OpsCoupons.vue'),
          meta: { title: '优惠券管理', requiresAuth: true, promotionPermission: true },
        },
        {
          path: 'orders',
          component: () => import('@/views/orders/OrderList.vue'),
          meta: { title: '我的订单', requiresAuth: true },
        },
        {
          path: 'orders/:no',
          component: () => import('@/views/orders/OrderDetail.vue'),
          props: true,
          meta: { title: '订单详情', requiresAuth: true },
        },
        {
          path: 'ops/orders',
          component: () => import('@/views/orders/OrderList.vue'),
          props: { ops: true },
          meta: { title: '订单履约', requiresAuth: true, fulfill: true },
        },
        {
          path: 'ops/orders/:no',
          component: () => import('@/views/orders/OrderDetail.vue'),
          props: (r) => ({ no: r.params.no, ops: true }),
          meta: { title: '订单履约详情', requiresAuth: true, fulfill: true },
        },
        {
          path: 'cart',
          component: () => import('@/views/cart/CartView.vue'),
          meta: { title: '购物车' },
        },
        {
          path: 'checkout',
          component: () => import('@/views/cart/CheckoutView.vue'),
          meta: { title: '结算预览', requiresAuth: true },
        },
        {
          path: '',
          name: 'home',
          component: () => import('@/views/catalog/CatalogList.vue'),
          alias: '/products',
          meta: { title: '首页' },
        },
        {
          path: 'products/:id',
          component: () => import('@/views/catalog/ProductDetail.vue'),
          props: true,
          meta: { title: '商品详情' },
        },
        {
          path: 'ops/products/:id/edit',
          component: () => import('@/views/catalog/ProductEditor.vue'),
          props: true,
          meta: { title: '维护商品', requiresAuth: true, catalogPermission: true },
        },
        {
          path: 'ops/products',
          component: () => import('@/views/catalog/CatalogList.vue'),
          props: { manage: true },
          meta: { title: '商品管理', requiresAuth: true, catalogPermission: true },
        },
        {
          path: 'status',
          component: () => import('@/views/home/Index.vue'),
          meta: { title: '服务状态' },
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
  if (to.meta.promotionPermission && !userStore.profile?.can_manage_promotions)
    return { name: 'account' }
  if (to.meta.fulfill && !userStore.profile?.can_fulfill_orders) return { name: 'account' }
  if (to.meta.catalogPermission && !userStore.profile?.can_manage_catalog)
    return { name: 'account' }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - SIQ优选商城` : 'SIQ优选商城'
})

export default router
