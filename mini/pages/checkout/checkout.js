const { request, uuid, KEYS } = require('../../utils/api')

const legacyKey = 'siq.mini.checkout.intent'
function accountKey() {
  const user = wx.getStorageSync(KEYS.user)
  return user && user.id ? `${legacyKey}.${user.id}` : null
}
function pendingFor(key) {
  if (!key) return null
  const item = wx.getStorageSync(key)
  if (item) return { storage: key, item }
  const legacy = wx.getStorageSync(legacyKey)
  if (legacy && wx.getStorageSync(key + '.excluded') !== legacy.intent_id) {
    return { storage: legacyKey, item: legacy }
  }
  return null
}

Page({
  data: { addresses: [], addressIndex: 0, cart: null, quote: null, couponId: null, couponOptions: [], couponIndex: 0, loading: true, error: '', notice: '', busy: false, recovering: false },
  onShow() { if (!this.submitting) this.load() },
  onHide() { this.generation = (this.generation || 0) + 1 },
  async load() {
    const generation = this.generation = (this.generation || 0) + 1
    const recovering = Boolean(pendingFor(accountKey()))
    this.setData({ loading: !recovering, recovering, addresses: [], addressIndex: 0, couponIndex: 0, couponOptions: [], couponId: null, cart: null, quote: null, busy: false, error: '' })
    if (recovering) return
    try {
      const [addresses, cart] = await Promise.all([
        request({ path: '/users/me/addresses/' }),
        request({ path: '/carts/items/' }),
      ])
      if (generation !== this.generation) return
      this.setData({ addresses, cart, loading: false })
      await this.quote()
    } catch (error) {
      if (generation === this.generation) this.setData({ error: error.message, loading: false })
    }
  },
  onAddress(event) {
    if (this.submitting) return
    this.setData({ addressIndex: Number(event.detail.value), couponId: null, couponIndex: 0 })
    return this.quote()
  },
  async quote() {
    const generation = this.generation = (this.generation || 0) + 1
    const address = this.data.addresses[this.data.addressIndex]
    const items = (this.data.cart?.items || []).filter(item => item.selected)
      .map(item => ({ sku_id: String(item.sku_id), quantity: item.quantity }))
    this.setData({ quote: null, busy: Boolean(address && items.length), error: '' })
    if (!address || !items.length) return
    try {
      const quote = await request({ path: '/checkout/quote/', method: 'POST', data: { address_id: String(address.id), items, user_coupon_id: this.data.couponId } })
      if (generation !== this.generation) return
      const couponOptions = [{ id: null, name: '不使用优惠券' }, ...quote.available_coupons]
      const selected = quote.selected_coupon
      if (selected && !couponOptions.some(option => option.id === selected.id)) couponOptions.push(selected)
      const couponIndex = couponOptions.findIndex(option => option.id === this.data.couponId)
      this.setData({ quote, couponOptions, couponIndex: Math.max(0, couponIndex), busy: false })
    } catch (error) {
      if (generation === this.generation) this.setData({ error: error.message, busy: false })
    }
  },
  onCoupon(event) {
    if (this.submitting) return
    const couponIndex = Number(event.detail.value)
    this.setData({ couponIndex, couponId: this.data.couponOptions[couponIndex].id })
    return this.quote()
  },
  async submit() {
    if (this.data.busy || this.submitting) return
    const key = accountKey()
    if (!key) return this.setData({ error: '请登录商城账号后继续结算。' })
    const saved = pendingFor(key)
    const quote = this.data.quote
    if (!saved && !quote) return
    if (!saved && Date.parse(quote.expires_at) <= Date.now()) {
      this.setData({ notice: '报价已过期，请核对更新后的金额。' })
      return this.quote()
    }
    const storage = saved ? saved.storage : key
    const item = saved ? saved.item : { intent_id: uuid(), key: uuid(), quote_id: quote.quote_id }
    this.submitting = true
    this.setData({ busy: true, error: '', notice: '' })
    try {
      wx.setStorageSync(storage, item)
      // place() checks the original intent before reading the quote or current cart.
      const order = await request({ path: '/orders/', method: 'POST', data: { intent_id: item.intent_id, quote_id: item.quote_id }, idempotencyKey: item.key })
      wx.removeStorageSync(storage)
      if (accountKey() === key) wx.redirectTo({ url: `/pages/order-detail/order-detail?no=${order.order_no}` })
    } catch (error) {
      if (accountKey() !== key) return
      const rejected = [400, 403, 404].includes(error.status) || [30001, 30002, 40004, 40005, 40006, 60002, 60003].includes(error.code)
      if (rejected) {
        // A legacy record has no owner. A foreign quote returns 404 and must remain recoverable by its buyer.
        if (storage === legacyKey && error.status === 404) wx.setStorageSync(key + '.excluded', item.intent_id)
        else if (storage !== legacyKey || error.status !== 403) wx.removeStorageSync(storage)
        this.setData({ notice: error.message + '。请重新核对购物车和报价。' })
        await this.load()
      } else {
        this.setData({ recovering: true, quote: null, error: error.message, notice: '提交结果待确认，请找回原订单。' })
      }
    } finally {
      this.submitting = false
      this.setData({ busy: false })
    }
  },
})
