import type { Address } from '@/types/models'
import request from '@/utils/request'

export interface AddressPayload {
  recipient: string
  phone: string
  province: string
  city: string
  district: string
  region_code: string
  detail: string
  is_default: boolean
}

export function fetchAddresses(): Promise<Address[]> {
  return request.get('/users/me/addresses/')
}

export function createAddress(payload: AddressPayload): Promise<Address> {
  return request.post('/users/me/addresses/', payload)
}

export function updateAddress(id: string, payload: Partial<AddressPayload>): Promise<Address> {
  return request.patch(`/users/me/addresses/${id}/`, payload)
}

export function deleteAddress(id: string, expectedVersion: number): Promise<null> {
  return request.delete(`/users/me/addresses/${id}/`, {
    data: { expected_version: expectedVersion },
  })
}

export function setDefaultAddress(id: string): Promise<Address> {
  return request.post(`/users/me/addresses/${id}/default/`, {})
}
