import type {
  Notice,
  NoticePage,
  NotificationTemplate,
  Page,
  ReadResult,
  Unread,
} from '@/types/models'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const notificationTypes: Record<string, string> = {
  order: '订单',
  support: '客服',
  system: '系统',
}

export const listNotifications = (params?: Record<string, string | number | undefined>): Promise<NoticePage> =>
  request.get('/notifications/', { params })

export const unreadNotifications = (): Promise<Unread> =>
  request.get('/notifications/unread-count/', { skipErrorMessage: true })

export const readNotifications = (data: Record<string, unknown>): Promise<ReadResult> =>
  request.post('/notifications/read/', data)

export const listTemplates = (
  params?: Record<string, string | number | undefined>,
): Promise<Page<NotificationTemplate>> => request.get('/ops/notification-templates/', { params })

export const reviseTemplate = (
  row: Pick<NotificationTemplate, 'id' | 'version'>,
  data: Record<string, unknown>,
): Promise<NotificationTemplate> =>
  request.patch(`/ops/notification-templates/${row.id}/`, {
    ...data,
    expected_version: row.version,
  })

export function activateTemplate(
  row: Pick<NotificationTemplate, 'id' | 'version'>,
  activeVersion: number,
): Promise<NotificationTemplate> {
  const storage = `siq.notification.template.${useUserStore().profile?.id}.${row.id}.${row.version}`
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post<NotificationTemplate>(
      `/ops/notification-templates/${row.id}/activate/`,
      { version: row.version, expected_version: activeVersion },
      { headers: { 'Idempotency-Key': key } },
    )
    .then((result) => {
      sessionStorage.removeItem(storage)
      return result
    })
    .catch((error: { response?: { status: number } }) => {
      if ([400, 403, 404, 409].includes(error.response?.status ?? 0))
        sessionStorage.removeItem(storage)
      throw error
    })
}

export function targetPath(notice: Pick<Notice, 'target_type' | 'target_id'>): string {
  const paths: Record<string, string> = {
    order: `/orders/${encodeURIComponent(notice.target_id)}`,
    support: `/support/${encodeURIComponent(notice.target_id)}`,
    review: '/account/reviews',
    announcement: `/announcements/${encodeURIComponent(notice.target_id)}`,
    page: `/pages/${encodeURIComponent(notice.target_id)}`,
    home: '/',
  }
  return paths[notice.target_type] || ''
}
