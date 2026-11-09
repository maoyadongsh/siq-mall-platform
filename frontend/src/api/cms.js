import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const cmsKinds = { banner: 'Banner', floor: '首页楼层', announcement: '公告', page: '单页' }
export const publicationStates = {
  draft: '草稿',
  scheduled: '定时待生效',
  online: '线上生效',
  expired: '已过有效期',
  offline: '已下线',
}

export const getHome = (platform = 'web') => request.get('/cms/home/', { params: { platform } })
export const getPublicContent = (kind, id, platform = 'web') =>
  request.get(`/cms/${kind === 'page' ? 'pages' : 'announcements'}/${id}/`, {
    params: { platform },
  })
export const listContents = (params) => request.get('/ops/cms/', { params })
export const getContent = (id) => request.get(`/ops/cms/${id}/`)
export const createContent = (data) => request.post('/ops/cms/', data)
export const saveDraft = (id, data) => request.patch(`/ops/cms/${id}/draft/`, data)
export const previewContent = (id, revision, platform) =>
  request.get(`/ops/cms/${id}/preview/`, { params: { revision, platform } })

export function publishContent(content, action, reason) {
  const revision = action === 'publish' ? content.latest_revision.revision_no : content.published_revision
  const storage = `siq.cms.${useUserStore().profile.id}.${action}.${content.id}.${content.version}.${revision}`
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post(
      `/ops/cms/${content.id}/${action}/`,
      { revision, expected_version: content.version, reason },
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

export function uploadMedia(file) {
  const data = new FormData()
  data.append('file', file)
  return request.post('/ops/media/', data)
}
