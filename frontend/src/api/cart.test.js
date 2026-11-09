import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { addGuest, guestCart, mergeGuest, removeGuest, updateGuest } from './cart'

vi.mock('@/utils/request', () => ({ default: { post: vi.fn() } }))

beforeEach(() => {
  const data = new Map()
  vi.stubGlobal('sessionStorage', {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
    removeItem: (key) => data.delete(key),
  })
  request.post.mockReset()
  addGuest({ title: '茶杯' }, { id: '7', label: '白', price: '99.00', available_stock: 10 }, 2)
})
afterEach(() => vi.unstubAllGlobals())

it('keeps the guest selection until a separate remove action', () => {
  for (const n of [0, NaN, 100]) expect(() => updateGuest('7', n)).toThrow()
  expect(guestCart().items[0].quantity).toBe(2)
  expect(removeGuest('7').items).toEqual([])
})

it('reuses the original merge after a lost response and binds it to the buyer', async () => {
  request.post.mockRejectedValueOnce(new Error('timeout'))
  await expect(mergeGuest('buyer-a')).rejects.toThrow('timeout')
  const first = request.post.mock.calls[0]
  expect(() => updateGuest('7', 3)).toThrow()
  await expect(mergeGuest('buyer-b')).rejects.toThrow()
  expect(request.post).toHaveBeenCalledTimes(1)
  request.post.mockResolvedValueOnce({ adjustments: [], requires_confirmation: false })
  await mergeGuest('buyer-a')
  expect(request.post.mock.calls[1]).toEqual(first)
  expect(guestCart().items).toEqual([])
})

it('retains the rejected quantity and the reason returned by the server', async () => {
  request.post.mockResolvedValueOnce({
    adjustments: [{ sku_id: '7', quantity: 2, reason: '库存不足' }],
    requires_confirmation: true,
  })
  const remaining = await mergeGuest('buyer-a')
  expect(remaining.items[0]).toMatchObject({ sku_id: '7', quantity: 2, reason: '库存不足' })
  expect(remaining.needsConfirmation).toBe(true)
})
