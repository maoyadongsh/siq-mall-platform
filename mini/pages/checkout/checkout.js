const { request, uuid } = require('../../utils/api')
Page({
  data: { addresses: [], addressIndex: 0, cart: null, quote: null, couponId: null, couponOptions: [], couponIndex: 0, loading: true, error: '', notice: '', busy: false },
  onLoad() { this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [addresses, cart] = await Promise.all([
        request({ path: '/users/me/addresses/' }),
        request({ path: '/carts/items/' }),
      ])
      this.setData({ addresses, cart, loading: false })
      if (addresses.length) this.quote()
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  onAddress(event) {
    this.setData({ addressIndex: Number(event.detail.value), quote: null })
    this.quote()
  },
  async quote() {
    const address = this.data.addresses[this.data.addressIndex]
    const items = this.data.cart.items.filter((item) => item.selected).map((item) => ({ sku_id: Number(item.sku_id), quantity: item.quantity }))
    if (!address || !items.length) return
    this.setData({ busy: true, error: '' })
    try {
      const quote = await request({ path: '/checkout/quote/', method: 'POST', data: { address_id: Number(address.id), items, user_coupon_id: this.data.couponId } })
      const couponOptions = [{ id: null, name: '不使用优惠券' }, ...quote.available_coupons]
      this.setData({ quote, couponOptions, busy: false })
    } catch (error) {
      this.setData({ error: error.message, busy: false })
    }
  },
  onCoupon(event) {
    const couponIndex = Number(event.detail.value)
    this.setData({ couponIndex, couponId: this.data.couponOptions[couponIndex].id, quote: null })
    this.quote()
  },
  async submit() {
    if (!this.data.quote || this.data.busy) return
    this.setData({ busy: true, error: '', notice: '' })
    const storage = 'siq.mini.checkout.intent'
    let pending = wx.getStorageSync(storage)
    if (!pending) pending = { intent_id: uuid(), key: uuid(), quote_id: this.data.quote.quote_id }
    if (pending.quote_id !== this.data.quote.quote_id) pending = { intent_id: uuid(), key: uuid(), quote_id: this.data.quote.quote_id }
    wx.setStorageSync(storage, pending)
    try {
      const order = await request({ path: '/orders/', method: 'POST', data: { intent_id: pending.intent_id, quote_id: pending.quote_id }, idempotencyKey: pending.key })
      wx.removeStorageSync(storage)
      wx.redirectTo({ url: `/pages/order-detail/order-detail?no=${order.order_no}` })
    } catch (error) {
      if ([400, 403, 404].includes(error.status)) wx.removeStorageSync(storage)
      this.setData({ error: error.message, busy: false, notice: error.type === 'network' ? '提交结果未知，请用原提交标识重试或到订单列表查询。' : '' })
    }
  },
})
