const test = require('node:test')
const assert = require('node:assert/strict')

function setup() {
  const storage = new Map()
  const calls = []
  global.wx = {
    getStorageSync: (key) => storage.get(key) || '',
    setStorageSync: (key, value) => storage.set(key, value),
    removeStorageSync: (key) => storage.delete(key),
    request(options) {
      calls.push(options)
      if (!this.succeed) return options.fail({ errMsg: 'offline' })
      options.success({ statusCode: 200, data: { code: 0, data: { adjustments: [], requires_confirmation: false } } })
    },
  }
  global.getApp = () => ({ globalData: { apiBaseUrl: 'http://test/api/v1' } })
  return { storage, calls }
}

test('guest cart enforces stock and retries a merge with the original batch key', async () => {
  const { calls } = setup()
  const cart = require('../utils/cart')
  const product = { id: '1', title: '茶杯' }
  const sku = { id: '2', label: '青绿', price: '99.00', available_stock: 2 }
  cart.add(product, sku, 1)
  assert.throws(() => cart.add(product, sku, 2), /超过可售库存/)
  wx.succeed = false
  await assert.rejects(cart.merge('42'))
  const firstKey = calls[0].header['Idempotency-Key']
  wx.succeed = true
  await cart.merge('42')
  assert.equal(calls[1].header['Idempotency-Key'], firstKey)
  assert.deepEqual(cart.read().items, [])
  assert.equal(cart.read().batch, null)
})
