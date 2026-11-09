import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const notificationTypes = { order: '订单', support: '客服', system: '系统' }

export const listNotifications = (params) => request.get('/notifications/', { params })
export const unreadNotifications = () =>
  request.get('/notifications/unread-count/', { skipErrorMessage: true })
export const readNotifications = (data) => request.post('/notifications/read/', data)
export const listTemplates = (params) => request.get('/ops/notification-templates/', { params })
export const reviseTemplate = (row, data) =>
  request.patch(`/ops/notification-templates/${row.id}/`, {
    ...data,
    expected_version: row.version,
  })

export function activateTemplate(row, activeVersion) {
  const storage = `siq.notification.template.${useUserStore().profile.id}.${row.id}.${row.version}`
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post(
      `/ops/notification-templates/${row.id}/activate/`,
      { version: row.version, expected_version: activeVersion },
      { headers: { 'Idempotency-Key': key } },
    )
    .then((result) => {
      sessionStorage.removeItem(storage)
      return result
    })
    .catch((error) => {
      if ([400, 403, 404, 409].includes(error.response?.status)) sessionStorage.removeItem(storage)
      throw error
    })
}

export function targetPath(notice) {
  const paths = {
    order: `/orders/${encodeURIComponent(notice.target_id)}`,
    support: `/support/${encodeURIComponent(notice.target_id)}`,
    review: '/account/reviews',
    announcement: `/announcements/${encodeURIComponent(notice.target_id)}`,
    page: `/pages/${encodeURIComponent(notice.target_id)}`,
    home: '/',
  }
  return paths[notice.target_type] || ''
}
