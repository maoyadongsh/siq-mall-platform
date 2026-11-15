import type { AuditRow, Page, RoleOption, RoleUser } from '@/types/models'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

export const getDashboard = (): Promise<Record<string, unknown>> => request.get('/ops/dashboard/')

export const getRoleUsers = (): Promise<RoleUser[]> => request.get('/ops/users/')

export const getRoleOptions = (): Promise<RoleOption[]> => request.get('/ops/role-options/')

export const getAudits = (
  params?: Record<string, string | number | undefined>,
): Promise<Page<AuditRow>> => request.get('/ops/audits/', { params })

export function updateUserRoles(
  user: Pick<RoleUser, 'id' | 'expected_version'>,
  roleIds: number[],
  reason: string,
): Promise<RoleUser> {
  const storage = `siq.roles.${useUserStore().profile?.id}.${user.id}.${user.expected_version}`
  const key = sessionStorage.getItem(storage) || crypto.randomUUID()
  sessionStorage.setItem(storage, key)
  return request
    .post<RoleUser>(
      `/ops/users/${user.id}/roles/`,
      { expected_version: user.expected_version, role_ids: roleIds, reason },
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
