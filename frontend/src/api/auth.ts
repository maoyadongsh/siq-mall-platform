import type { SessionData, UserSummary } from '@/types/models'
import request from '@/utils/request'

export interface LoginCredentials {
  identifier: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  accepted_terms_version: string
  captcha_id?: string
  captcha_code?: string
}

export function login(credentials: LoginCredentials): Promise<SessionData> {
  return request.post('/auth/login/', credentials)
}

export function register(payload: RegisterPayload): Promise<SessionData> {
  return request.post('/auth/register/', payload)
}

export function logout(scope: 'current' | 'all' = 'current'): Promise<null> {
  return request.post('/auth/logout/', { scope })
}

export function fetchMe(): Promise<UserSummary> {
  return request.get('/users/me/')
}

export function updateProfile(payload: Record<string, unknown>): Promise<UserSummary> {
  return request.patch('/users/me/', payload)
}
