import request from '@/utils/request'

const guestKey = 'siq.guest-cart.v1'
const blank = () => ({ items: [], batch: null, needsConfirmation: false })
export function guestCart() {
  const raw = sessionStorage.getItem(guestKey)
  return raw ? JSON.parse(raw) : blank()
}
function store(cart) {
  sessionStorage.setItem(guestKey, JSON.stringify(cart))
  return cart
}
export function addGuest(product, sku, quantity) {
  const cart = guestCart()
  if (cart.batch) throw new Error('请先到购物车确认上次合并结果')
  const item = cart.items.find((i) => i.sku_id === sku.id)
  const sum = (item?.quantity || 0) + quantity
  if (sum > 99 || sum > sku.available_stock) throw new Error('加入数量超过可售库存或99件上限')
  if (!item && cart.items.length >= 50) throw new Error('最多加入50种规格')
  if (item) item.quantity = sum
  else
    cart.items.push({
      sku_id: sku.id,
      title: product.title,
      label: sku.label,
      current_price: sku.price,
      quantity,
    })
  return store(cart)
}
export function updateGuest(id, quantity) {
  const cart = guestCart()
  if (cart.batch) throw new Error('请先确认上次合并结果')
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 99)
    throw new Error('数量须为1至99的整数')
  const item = cart.items.find((i) => i.sku_id === id)
  if (item) item.quantity = quantity
  return store(cart)
}

export function removeGuest(id) {
  const cart = guestCart()
  if (cart.batch) throw new Error('请先确认上次合并结果')
  cart.items = cart.items.filter((i) => i.sku_id !== id)
  return store(cart)
}

export async function mergeGuest(userId) {
  const cart = guestCart()
  if (!cart.items.length) return cart
  if (cart.batch && cart.batch.owner !== userId)
    throw new Error('请使用上次合并购物车的账号确认结果')
  if (!cart.batch) {
    cart.batch = {
      owner: userId,
      key: crypto.randomUUID(),
      items: cart.items.map(({ sku_id, quantity }) => ({ sku_id, quantity })),
    }
    store(cart)
  }
  const data = await request.post(
    '/carts/merge/',
    { items: cart.batch.items },
    { headers: { 'Idempotency-Key': cart.batch.key } },
  )
  const reasons = new Map(data.adjustments.map((r) => [r.sku_id, r.reason]))
  return store({
    items: cart.items
      .filter((i) => reasons.has(i.sku_id))
      .map((i) => ({ ...i, reason: reasons.get(i.sku_id) })),
    batch: null,
    needsConfirmation: data.requires_confirmation,
  })
}

export function pendingAdd(userId) {
  return JSON.parse(sessionStorage.getItem('siq.cart.add.' + userId) || 'null')
}
export async function addMember(userId, line) {
  const storage = 'siq.cart.add.' + userId
  const op = pendingAdd(userId) || { key: crypto.randomUUID(), line }
  sessionStorage.setItem(storage, JSON.stringify(op))
  try {
    const result = await request.post('/carts/items/', op.line, {
      headers: { 'Idempotency-Key': op.key },
    })
    sessionStorage.removeItem(storage)
    return result
  } catch (e) {
    if ([400, 404, 409].includes(e.response?.status)) sessionStorage.removeItem(storage)
    throw e
  }
}
export const getCart = () => request.get('/carts/items/')
export const patchItem = (item, changes) =>
  request.patch('/carts/items/' + item.id + '/', { ...changes, expected_version: item.version })
export const deleteItem = (item) =>
  request.delete('/carts/items/' + item.id + '/', { data: { expected_version: item.version } })
export const quote = (address_id, items) =>
  request.post('/checkout/quote/', {
    address_id,
    items: items.map(({ sku_id, quantity }) => ({ sku_id, quantity })),
  })
