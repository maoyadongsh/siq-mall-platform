const KEY = 'siq.mini.guest-cart'
const { uuid, request } = require('./api')

function read() {
  return wx.getStorageSync(KEY) || { items: [], batch: null }
}
function write(cart) {
  wx.setStorageSync(KEY, cart)
  return cart
}
function add(product, sku, quantity = 1) {
  const cart = read()
  const existing = cart.items.find((item) => item.sku_id === sku.id)
  const current = existing ? existing.quantity : 0
  if (current + quantity > 99 || current + quantity > sku.available_stock) throw new Error('数量超过可售库存或99件上限')
  if (existing) existing.quantity += quantity
  else cart.items.push({ sku_id: sku.id, title: product.title, label: sku.label, current_price: sku.price, quantity })
  return write(cart)
}
function update(skuId, quantity) {
  const cart = read()
  const item = cart.items.find((row) => row.sku_id === skuId)
  if (item) item.quantity = Math.max(1, Math.min(99, Number(quantity)))
  return write(cart)
}
function remove(skuId) {
  const cart = read()
  cart.items = cart.items.filter((row) => row.sku_id !== skuId)
  return write(cart)
}
async function merge(userId) {
  const cart = read()
  if (!cart.items.length) return cart
  if (!cart.batch) cart.batch = { owner: userId, key: uuid(), items: cart.items.map(({ sku_id, quantity }) => ({ sku_id, quantity })) }
  if (cart.batch.owner !== userId) throw new Error('请使用原账号确认游客购物车')
  write(cart)
  const data = await request({ path: '/carts/merge/', method: 'POST', data: { items: cart.batch.items }, idempotencyKey: cart.batch.key })
  const rejected = new Map(data.adjustments.map((row) => [row.sku_id, row.reason]))
  return write({
    items: cart.items.filter((item) => rejected.has(item.sku_id)).map((item) => ({ ...item, reason: rejected.get(item.sku_id) })),
    batch: null,
  })
}
module.exports = { read, write, add, update, remove, merge }
