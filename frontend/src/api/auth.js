import request from '@/utils/request'

export function login(credentials) {
  return request.post('/auth/login/', credentials)
}

export function register(payload) {
  return request.post('/auth/register/', payload)
}

export function logout(scope = 'current') {
  return request.post('/auth/logout/', { scope })
}

export function fetchMe() {
  return request.get('/users/me/')
}

export function updateProfile(payload) {
  return request.patch('/users/me/', payload)
}
