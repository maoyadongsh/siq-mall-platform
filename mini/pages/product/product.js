const { request, isLoggedIn, uuid } = require('../../utils/api')
const cart = require('../../utils/cart')
Page({
  data: { id: '', product: null, sku: null, quantity: 1, loading: true, error: '', notice: '', busy: false },
  onLoad(options) { this.setData({ id: options.id }); this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const product = await request({ path: `/products/${this.data.id}/`, auth: false })
      const available = product.skus.find((sku) => sku.available_stock > 0) || product.skus[0]
      this.setData({ product, sku: available, loading: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  onSku(event) {
    const sku = this.data.product.skus.find((row) => row.id === event.currentTarget.dataset.id)
    this.setData({ sku })
  },
  onQuantity(event) { this.setData({ quantity: Math.max(1, Math.min(99, Number(event.detail.value) || 1)) }) },
  async add() {
    const { product, sku, quantity } = this.data
    if (!sku || !sku.available_stock || this.data.busy) return
    this.setData({ busy: true, error: '', notice: '' })
    if (!isLoggedIn()) {
      cart.add(product, sku, quantity)
      this.setData({ notice: '已加入游客购物车，登录后可合并', busy: false })
      return
    }
    const storage = `siq.mini.add.${sku.id}`
    const key = wx.getStorageSync(storage) || uuid()
    wx.setStorageSync(storage, key)
    try {
      await request({ path: '/carts/items/', method: 'POST', data: { sku_id: Number(sku.id), quantity }, idempotencyKey: key })
      wx.removeStorageSync(storage)
      this.setData({ notice: '已加入购物车', busy: false })
    } catch (error) {
      if ([400, 403, 404, 409].includes(error.status)) wx.removeStorageSync(storage)
      this.setData({ error: error.message, busy: false })
    }
  },
  onShareAppMessage() {
    return { title: this.data.product ? this.data.product.title : 'SIQ优选商城', path: `/pages/product/product?id=${this.data.id}` }
  },
})
