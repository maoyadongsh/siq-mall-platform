const test = require('node:test')
const assert = require('node:assert/strict')

function harness() {
  const storage = new Map()
  const calls = []
  global.wx = {
    getStorageSync: (key) => storage.get(key) || '',
    setStorageSync: (key, value) => storage.set(key, value),
    removeStorageSync: (key) => storage.delete(key),
    request(options) {
      calls.push(options)
      const route = routes.get(options.url) || routes.get('default')
      route(options)
    },
  }
  const routes = new Map()
  global.getApp = () => ({ globalData: { apiBaseUrl: 'http://test/api/v1' } })
  return { storage, calls, routes }
}
function respond(options, statusCode, data) {
  options.success({ statusCode, data })
}
test('concurrent 401 responses share one refresh and replay only reads', async () => {
  const { calls, routes } = harness()
  const { request, login } = require('../utils/api')
  let productsCalls = 0
  routes.set('http://test/api/v1/auth/mini/login/', (options) => respond(options, 200, { code: 0, data: { access: 'old', refresh: 'old-refresh', session_id: 's', user: { id: '1' } } }))
  routes.set('http://test/api/v1/auth/mini/refresh/', (options) => setTimeout(() => respond(options, 200, { code: 0, data: { access: 'new', refresh: 'new-refresh', session_id: 's', user: { id: '1' } } }), 10))
  routes.set('http://test/api/v1/products/', (options) => {
    productsCalls += 1
    if (productsCalls <= 2) respond(options, 401, { code: 10002, message: 'expired' })
    else respond(options, 200, { code: 0, data: { results: [] } })
  })
  await login('buyer', 'password')
  await Promise.all([request({ path: '/products/' }), request({ path: '/products/' })])
  assert.equal(calls.filter((call) => call.url.endsWith('/auth/mini/refresh/')).length, 1)
  assert.equal(productsCalls, 4)
})

test('a 401 write is not automatically replayed after refresh', async () => {
  const { calls, routes, storage } = harness()
  const { request } = require('../utils/api')
  routes.set('http://test/api/v1/auth/mini/refresh/', (options) => respond(options, 200, { code: 0, data: { access: 'new', refresh: 'new-refresh', session_id: 's', user: { id: '1' } } }))
  routes.set('http://test/api/v1/orders/', (options) => respond(options, 401, { code: 10002, message: 'expired' }))
  storage.set('siq.mini.refresh', 'old-refresh')
  await assert.rejects(request({ path: '/orders/', method: 'POST', data: {} }), (error) => error.status === 401)
  assert.equal(calls.filter((call) => call.url.endsWith('/orders/')).length, 1)
})

test('network failures preserve a caller-owned idempotency key and logout clears session', async () => {
  const { routes, storage } = harness()
  const { request, logout, uuid } = require('../utils/api')
  const key = uuid()
  routes.set('http://test/api/v1/conversations/1/messages/', (options) => options.fail({ errMsg: 'offline' }))
  await assert.rejects(request({ path: '/conversations/1/messages/', method: 'POST', data: {}, idempotencyKey: key }), (error) => error.type === 'network')
  assert.match(key, /^[0-9a-f-]{36}$/)
  routes.set('http://test/api/v1/auth/mini/logout/', (options) => respond(options, 200, { code: 0, data: null }))
  storage.set('siq.mini.refresh', 'refresh')
  await logout()
  assert.equal(storage.has('siq.mini.refresh'), false)
})
