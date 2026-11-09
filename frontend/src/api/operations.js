import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const getDashboard = () => request.get('/ops/dashboard/')
export const getRoleUsers = () => request.get('/ops/users/')
export const getRoleOptions = () => request.get('/ops/role-options/')
export const getAudits = (params) => request.get('/ops/audits/', { params })

export function updateUserRoles(user, roleIds, reason) {
  const storage = `siq.roles.${useUserStore().profile.id}.${user.id}.${user.expected_version}`
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post(
      `/ops/users/${user.id}/roles/`,
      { expected_version: user.expected_version, role_ids: roleIds, reason },
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
