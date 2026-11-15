import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    moderation?: boolean
    promotionPermission?: boolean
    fulfill?: boolean
    catalogPermission?: boolean
    contentPermission?: boolean
    supportPermission?: boolean
    rolesPermission?: boolean
    auditPermission?: boolean
  }
}
