import request from '@/utils/request'

export function fetchAddresses() {
  return request.get('/users/me/addresses/')
}

export function createAddress(payload) {
  return request.post('/users/me/addresses/', payload)
}

export function updateAddress(id, payload) {
  return request.patch(`/users/me/addresses/${id}/`, payload)
}

export function deleteAddress(id, expectedVersion) {
  return request.delete(`/users/me/addresses/${id}/`, {
    data: { expected_version: expectedVersion },
  })
}

export function setDefaultAddress(id) {
  return request.post(`/users/me/addresses/${id}/default/`, {})
}
