import type {
  CartData,
  CartItem,
  GuestCart,
  GuestCartLine,
  Product,
  QuoteData,
  Sku,
} from '@/types/models'
import request from '@/utils/request'

const guestKey = 'siq.guest-cart.v1'
const blank = (): GuestCart => ({ items: [], batch: null, needsConfirmation: false })

export function guestCart(): GuestCart {
  const raw = sessionStorage.getItem(guestKey)
  return raw ? (JSON.parse(raw) as GuestCart) : blank()
}

function store(cart: GuestCart): GuestCart {
  sessionStorage.setItem(guestKey, JSON.stringify(cart))
  return cart
}

export function addGuest(product: Pick<Product, 'title'>, sku: Sku, quantity: number): GuestCart {
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

export function updateGuest(id: string, quantity: number): GuestCart {
  const cart = guestCart()
  if (cart.batch) throw new Error('请先确认上次合并结果')
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 99)
    throw new Error('数量须为1至99的整数')
  const item = cart.items.find((i) => i.sku_id === id)
  if (item) item.quantity = quantity
  return store(cart)
}

export function removeGuest(id: string): GuestCart {
  const cart = guestCart()
  if (cart.batch) throw new Error('请先确认上次合并结果')
  cart.items = cart.items.filter((i) => i.sku_id !== id)
  return store(cart)
}

interface MergeResult {
  adjustments: { sku_id: string; reason: string }[]
  requires_confirmation: boolean
}

export async function mergeGuest(userId: string): Promise<GuestCart> {
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
  const data = await request.post<MergeResult>(
    '/carts/merge/',
    { items: cart.batch.items },
    { headers: { 'Idempotency-Key': cart.batch.key } },
  )
  const reasons = new Map(data.adjustments.map((r) => [r.sku_id, r.reason]))
  return store({
    items: cart.items
      .filter((i) => reasons.has(i.sku_id))
      .map((i): GuestCartLine & { reason?: string } => ({ ...i, reason: reasons.get(i.sku_id) })),
    batch: null,
    needsConfirmation: data.requires_confirmation,
  })
}

interface PendingAdd {
  key: string
  line: Record<string, unknown>
}

export function pendingAdd(userId: string): PendingAdd | null {
  return JSON.parse(sessionStorage.getItem('siq.cart.add.' + userId) || 'null') as PendingAdd | null
}

export async function addMember(userId: string, line: Record<string, unknown>): Promise<CartItem> {
  const storage = 'siq.cart.add.' + userId
  const op = pendingAdd(userId) || { key: crypto.randomUUID(), line }
  sessionStorage.setItem(storage, JSON.stringify(op))
  try {
    const result = await request.post<CartItem>('/carts/items/', op.line, {
      headers: { 'Idempotency-Key': op.key },
    })
    sessionStorage.removeItem(storage)
    return result
  } catch (e) {
    const error = e as { response?: { status: number } }
    if ([400, 404, 409].includes(error.response?.status ?? 0)) sessionStorage.removeItem(storage)
    throw e
  }
}

export const getCart = (): Promise<CartData> => request.get('/carts/items/')

export const patchItem = (item: CartItem, changes: Record<string, unknown>): Promise<CartItem> =>
  request.patch('/carts/items/' + item.id + '/', { ...changes, expected_version: item.version })

export const deleteItem = (item: CartItem): Promise<null> =>
  request.delete('/carts/items/' + item.id + '/', { data: { expected_version: item.version } })

export const quote = (
  address_id: string,
  items: { sku_id: string; quantity: number }[],
  user_coupon_id: string | null = null,
): Promise<QuoteData> =>
  request.post('/checkout/quote/', {
    address_id,
    user_coupon_id,
    items: items.map(({ sku_id, quantity }) => ({ sku_id, quantity })),
  })
