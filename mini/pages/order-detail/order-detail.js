const { request, uuid } = require('../../utils/api')
Page({
  data: { no: '', order: null, loading: true, error: '', notice: '', busy: false },
  onLoad(options) { this.setData({ no: options.no }) },
  onShow() { if (this.data.no) this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const order = await request({ path: `/orders/${this.data.no}/` })
      this.setData({ order, loading: false, busy: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  async command(path, storage, data = {}) {
    this.setData({ busy: true, error: '', notice: '' })
    const key = wx.getStorageSync(storage) || uuid()
    wx.setStorageSync(storage, key)
    try {
      await request({ path, method: 'POST', data, idempotencyKey: key })
      wx.removeStorageSync(storage)
      await this.load()
    } catch (error) {
      if ([400, 403, 404, 409].includes(error.status)) wx.removeStorageSync(storage)
      this.setData({ error: error.message, busy: false })
    }
  },
  async pay(event) {
    const outcome = event.currentTarget.dataset.outcome
    const createKey = `siq.mini.payment.create.${this.data.no}`
    const key = wx.getStorageSync(createKey) || uuid()
    wx.setStorageSync(createKey, key)
    try {
      this.setData({ busy: true, error: '' })
      const payment = await request({ path: '/payments/', method: 'POST', data: { order_no: this.data.no }, idempotencyKey: key })
      wx.removeStorageSync(createKey)
      await this.command(`/payments/${payment.pay_no}/simulate/`, `siq.mini.payment.${payment.pay_no}.${outcome}`, { outcome })
      this.setData({ notice: outcome === 'success' ? '模拟支付成功' : '本次模拟支付失败，可重新创建支付尝试' })
    } catch (error) {
      this.setData({ error: error.message, busy: false })
    }
  },
  cancel() { this.command(`/orders/${this.data.no}/cancel/`, `siq.mini.cancel.${this.data.no}`, { reason: 'user_changed_mind' }) },
  receive() { this.command(`/orders/${this.data.no}/receive/`, `siq.mini.receive.${this.data.no}`) },
  unavailable() { wx.showToast({ title: '订阅模板未配置，站内消息仍可用', icon: 'none' }) },
})
