// Run with node --test qa/acceptance/mini-boundaries.cjs. No platform account needed.
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const assert = require('node:assert/strict')

function harness(request, storage = new Map([['siq.mini.user', { id: 'buyer' }]])) {
  let id = 0
  const wx = {
    getStorageSync: k => storage.get(k),
    setStorageSync: (k, v) => storage.set(k, v),
    removeStorageSync: k => storage.delete(k),
    redirectTo() {},
  }
  return name => {
    let page
    const source = path.join(__dirname, '../../mini/pages', name, name + '.js')
    vm.runInNewContext(fs.readFileSync(source, 'utf8'), {
      Page: value => { page = value },
      wx, setInterval, clearInterval,
      require: () => ({ request, KEYS: {user:'siq.mini.user'}, uuid: () => 'id-' + ++id }),
    })
    page.setData = changes => Object.assign(page.data, changes)
    return page
  }
}

test('a rejected simulation cannot produce a success notice', async () => {
  let simulations = 0
  const page = harness(async options => {
    if (options.path === '/payments/') return { pay_no: 'test', status: 'init' }
    if (options.path.endsWith('/simulate/')) simulations++
    throw { status: 409, message: 'rejected' }
  })('order-detail')
  page.data.no = 'order'
  await page.pay({currentTarget: {dataset: {outcome: 'success'}}})
  assert.equal(simulations, 1)
  assert.equal(page.data.error, 'rejected')
  assert.doesNotMatch(page.data.notice, /支付成功/)
})

test('an ordinary send tap submits the current draft', async () => {
  let sent = 0
  const page = harness(async options => {
    if (options.method === 'POST' && options.path.endsWith('/messages/')) sent++
    return {id: '1', results: [], poll_cursor: null}
  })('support')
  page.data.conversation = {id: '1', status: 'open'}
  page.data.draft = '咨询库存'
  await page.send({currentTarget: {dataset: {}}})
  assert.equal(sent, 1)
})

test('a new quote cannot replace an order submission whose result is unknown', async () => {
  const posts = []
  const make = harness(async options => {
    if (options.path === '/orders/') posts.push([options.data.intent_id, options.data.quote_id, options.idempotencyKey])
    throw {type: 'network', message: 'timeout'}
  })
  for (const quote_id of ['previous', 'new']) {
    const page = make('checkout')
    page.data.quote = {quote_id}
    await page.submit()
  }
  assert.equal(posts.length, 2)
  assert.equal(posts[1][1], 'previous')
  assert.equal(new Set(posts.map(JSON.stringify)).size, 1)
})

test('an older quote response cannot overwrite the selected address quote', async () => {
  const responses = []
  const page = harness(() => new Promise(resolve => responses.push(resolve)))('checkout')
  page.data.addresses = [{id:'1'}, {id:'2'}]
  page.data.cart = {items:[{sku_id:'1', quantity:1, selected:true}]}
  const first = page.quote()
  page.data.addressIndex = 1
  const second = page.quote()
  responses[1]({quote_id:'B', available_coupons:[]})
  await second
  responses[0]({quote_id:'A', available_coupons:[]})
  await first
  assert.equal(page.data.quote?.quote_id, 'B')
})

test('cold checkout recovers the matching account even after the cart was cleared', async () => {
  const storage = new Map()
  const calls = []
  const make = harness(async options => {
    calls.push(options)
    if (calls.length <= 2) throw { status: 409, code: 10009, message: 'busy' }
    return { order_no: 'recovered' }
  }, storage)
  for (const buyer of ['alice', 'bob', 'alice']) {
    storage.set('siq.mini.user', { id: buyer })
    const page = make('checkout')
    if (calls.length < 2) page.data.quote = { quote_id: buyer + '-quote' }
    else {
      await page.load()
      assert.equal(page.data.recovering, true)
      assert.equal(page.data.cart, null)
    }
    await page.submit()
  }
  assert.equal(calls.length, 3)
  assert.equal(calls[0].idempotencyKey, calls[2].idempotencyKey)
  assert.equal(calls[0].data.quote_id, calls[2].data.quote_id)
  assert.notEqual(calls[0].idempotencyKey, calls[1].idempotencyKey)
  assert.ok(storage.get('siq.mini.checkout.intent.bob'))
  assert.equal(storage.has('siq.mini.checkout.intent.alice'), false)
})

test('payment timeout queries original attempt and reports its settled outcome', async () => {
  const paths = []
  const make = harness(async options => {
    paths.push(options.path)
    if (options.path === '/payments/') return { pay_no: 'p', status: 'init' }
    if (options.path.endsWith('/simulate/')) throw { type: 'network', message: 'timeout' }
    if (options.path === '/payments/p/') return { status: 'success', order_status: 'paid' }
    return { status: 'paid' }
  })
  for (const outcome of ['success', 'failed']) {
    const page = make('order-detail')
    page.data.no = 'demo'
    await page.pay({ currentTarget: { dataset: { outcome } } })
    if (outcome === 'failed') assert.match(page.data.notice, /模拟支付成功/)
    else assert.doesNotMatch(page.data.notice, /支付成功/)
  }
  assert.deepEqual(paths, ['/payments/', '/payments/p/simulate/', '/payments/p/', '/orders/demo/'])
})

test('retry from a failed chat bubble preserves the exact original message', async () => {
  const sent = []
  const page = harness(async options => {
    if (options.method === 'POST' && options.path.endsWith('/messages/')) {
      sent.push([options.data.client_message_id, options.idempotencyKey, options.data.body])
      if (sent.length === 1) throw {type:'network', message:'timeout'}
    }
    return {id:'1', results:[], poll_cursor:null}
  })('support')
  page.data.conversation = {id:'1', status:'open'}
  page.data.draft = '咨询物流'
  await page.send({currentTarget:{dataset:{}}})
  const failed = page.data.pending[0]
  assert.equal(failed.state, 'failed')
  page.data.draft = '下一条草稿'
  await page.send({currentTarget:{dataset:{item:{...failed}}}})
  assert.deepEqual(sent[0], sent[1])
  assert.equal(page.data.pending.length, 0)
  assert.equal(page.data.draft, '下一条草稿')
})

test('a foreign legacy checkout remains available to its owner', async () => {
  const original = { intent_id: 'legacy-intent', key: 'legacy-key', quote_id: 'alice-quote' }
  const storage = new Map([['siq.mini.checkout.intent', original]])
  const attempts = []
  const make = harness(async options => {
    if (options.path !== '/orders/') return options.path.includes('addresses') ? [] : {items:[]}
    attempts.push([options.data.quote_id, options.idempotencyKey])
    if (storage.get('siq.mini.user').id === 'bob') throw {status:404, message:'报价不存在'}
    return {order_no:'alice-order'}
  }, storage)
  storage.set('siq.mini.user', {id:'bob'})
  const bob = make('checkout')
  await bob.load()
  await bob.submit()
  assert.equal(bob.data.recovering, false)
  assert.ok(storage.get('siq.mini.checkout.intent'))
  storage.set('siq.mini.user', {id:'alice'})
  const alice = make('checkout')
  await alice.load()
  assert.equal(alice.data.recovering, true)
  await alice.submit()
  assert.deepEqual(attempts, [['alice-quote','legacy-key'], ['alice-quote','legacy-key']])
  assert.equal(storage.has('siq.mini.checkout.intent'), false)
})

test('changing coupon blocks submission until the matching quote arrives', async () => {
  const quotes = []
  const orders = []
  const page = harness(options => {
    if (options.path === '/orders/') {
      orders.push(options.data.quote_id)
      return Promise.resolve({order_no:'order'})
    }
    return new Promise(resolve => quotes.push(resolve))
  })('checkout')
  page.data.addresses = [{id:'1'}]
  page.data.cart = {items:[{sku_id:'1', quantity:1, selected:true}]}
  const coupons = [{id:null,name:'不用券'}, {id:'1',name:'减5元'}]
  page.data.couponOptions = coupons
  const first = page.onCoupon({detail:{value:1}})
  const latest = page.onCoupon({detail:{value:0}})
  quotes[0]({quote_id:'with-discount', available_coupons:coupons.slice(1)})
  await first
  await page.submit()
  assert.equal(orders.length, 0)
  quotes[1]({quote_id:'no-discount', available_coupons:coupons.slice(1)})
  await latest
  await page.submit()
  assert.deepEqual(orders, ['no-discount'])
})
