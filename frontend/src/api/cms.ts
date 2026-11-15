import type { Content, Page, PublicContent, Revision } from '@/types/models'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const cmsKinds: Record<string, string> = {
  banner: 'Banner',
  floor: '首页楼层',
  announcement: '公告',
  page: '单页',
}

export const publicationStates: Record<string, string> = {
  draft: '草稿',
  scheduled: '定时待生效',
  online: '线上生效',
  expired: '已过有效期',
  offline: '已下线',
}

export const getHome = (platform = 'web'): Promise<Record<string, unknown>> =>
  request.get('/cms/home/', { params: { platform } })

export const getPublicContent = (
  kind: string,
  id: string,
  platform = 'web',
): Promise<PublicContent> =>
  request.get(`/cms/${kind === 'page' ? 'pages' : 'announcements'}/${id}/`, {
    params: { platform },
  })

export const listContents = (
  params?: Record<string, string | number | undefined>,
): Promise<Page<Content>> => request.get('/ops/cms/', { params })

export const getContent = (id: string): Promise<Content> => request.get(`/ops/cms/${id}/`)

export const createContent = (data: Record<string, unknown>): Promise<Content> =>
  request.post('/ops/cms/', data)

export const saveDraft = (id: string, data: Record<string, unknown>): Promise<Content> =>
  request.patch(`/ops/cms/${id}/draft/`, data)

export const previewContent = (
  id: string,
  revision: number,
  platform: string,
): Promise<{ revision: Revision; blocks: Record<string, unknown>[] }> =>
  request.get(`/ops/cms/${id}/preview/`, { params: { revision, platform } })

export interface PublishableContent {
  id: string
  version: number
  latest_revision: { revision_no: number }
  published_revision: number | null
}

export function publishContent(
  content: PublishableContent,
  action: string,
  reason: string,
): Promise<Content> {
  const revision =
    action === 'publish' ? content.latest_revision.revision_no : content.published_revision
  const storage = `siq.cms.${useUserStore().profile?.id}.${action}.${content.id}.${content.version}.${revision}`
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post<Content>(
      `/ops/cms/${content.id}/${action}/`,
      { revision, expected_version: content.version, reason },
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

export function uploadMedia(file: File): Promise<Record<string, unknown>> {
  const data = new FormData()
  data.append('file', file)
  return request.post('/ops/media/', data)
}
