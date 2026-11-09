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
          path: 'ops/cms',
          component: () => import('@/views/content/OpsCmsList.vue'),
          meta: { title: '内容管理', requiresAuth: true, contentPermission: true },
        },
        {
          path: 'ops/cms/:id/edit',
          component: () => import('@/views/content/OpsCmsEditor.vue'),
          props: true,
          meta: { title: '内容编辑与发布', requiresAuth: true, contentPermission: true },
        },
        {
          path: 'pages/:identifier',
          component: () => import('@/views/content/ContentPage.vue'),
          props: (route) => ({ kind: 'page', identifier: route.params.identifier }),
          meta: { title: '商城单页' },
        },
        {
          path: 'announcements/:identifier',
          component: () => import('@/views/content/ContentPage.vue'),
          props: (route) => ({ kind: 'announcement', identifier: route.params.identifier }),
          meta: { title: '商城公告' },
        },
        {
          path: 'messages',
          component: () => import('@/views/notifications/MessageCenter.vue'),
          meta: { title: '消息中心', requiresAuth: true },
        },
        {
          path: 'ops/notification-templates',
          component: () => import('@/views/notifications/OpsTemplates.vue'),
          meta: { title: '通知模板', requiresAuth: true, contentPermission: true },
        },
        {
          path: 'orders/:no/review',
          component: () => import('@/views/reviews/OrderReview.vue'),
          props: true,
          meta: { title: '评价订单商品', requiresAuth: true },
        },
        {
          path: 'account/reviews',
          component: () => import('@/views/reviews/ReviewList.vue'),
          meta: { title: '我的评价', requiresAuth: true },
        },
        {
          path: 'ops/reviews',
          component: () => import('@/views/reviews/ReviewList.vue'),
          props: { ops: true },
          meta: { title: '评价审核', requiresAuth: true, moderation: true },
        },
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
          component: () => import('@/views/content/HomeView.vue'),
          meta: { title: '首页' },
        },
        {
          path: 'products',
          component: () => import('@/views/catalog/CatalogList.vue'),
          meta: { title: '选购商品' },
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
  if (to.meta.moderation && !userStore.profile?.can_moderate_reviews) return { name: 'account' }
  if (to.meta.promotionPermission && !userStore.profile?.can_manage_promotions)
    return { name: 'account' }
  if (to.meta.fulfill && !userStore.profile?.can_fulfill_orders) return { name: 'account' }
  if (to.meta.catalogPermission && !userStore.profile?.can_manage_catalog)
    return { name: 'account' }
  if (to.meta.contentPermission && !userStore.profile?.can_publish_content)
    return { name: 'account' }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - SIQ优选商城` : 'SIQ优选商城'
})

export default router
