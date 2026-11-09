const { request, uuid } = require('../../utils/api')
Page({
  data: { no: '', order: null, loading: true, error: '', notice: '', busy: false, pendingPayment: false },
  onLoad(options) { this.setData({ no: options.no }) },
  onShow() {
    this.setData({ pendingPayment: Boolean(wx.getStorageSync(`siq.mini.payment.attempt.${this.data.no}`)) })
    if (this.data.no) this.load()
  },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const order = await request({ path: `/orders/${this.data.no}/` })
      this.setData({ order, loading: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  async command(path, storage, data = {}) {
    if (this.data.busy) return
    this.setData({ busy: true, error: '', notice: '' })
    const key = wx.getStorageSync(storage) || uuid()
    wx.setStorageSync(storage, key)
    try {
      await request({ path, method: 'POST', data, idempotencyKey: key })
      wx.removeStorageSync(storage)
      await this.load()
    } catch (error) {
      if ([400, 403, 404, 409].includes(error.status) && error.code !== 10009) wx.removeStorageSync(storage)
      this.setData({ error: error.message })
    } finally { this.setData({ busy: false }) }
  },
  async pay(event) {
    if (this.data.busy) return
    const storage = `siq.mini.payment.attempt.${this.data.no}`
    const createKey = `siq.mini.payment.create.${this.data.no}`
    const saved = wx.getStorageSync(storage)
    const attempt = saved || { outcome: event.currentTarget.dataset.outcome, createKey: wx.getStorageSync(createKey) || uuid(), key: uuid() }
    this.setData({ busy: true, error: '', notice: '' })
    try {
      wx.setStorageSync(storage, attempt)
      this.setData({ pendingPayment: true })
      let payment
      if (attempt.payNo) {
        payment = await request({ path: `/payments/${attempt.payNo}/` })
      } else {
        payment = await request({ path: '/payments/', method: 'POST', data: { order_no: this.data.no }, idempotencyKey: attempt.createKey })
        attempt.payNo = payment.pay_no
        wx.setStorageSync(storage, attempt)
        wx.removeStorageSync(createKey)
      }
      if (payment.status === 'init') {
        payment = await request({ path: `/payments/${attempt.payNo}/simulate/`, method: 'POST', data: { outcome: attempt.outcome }, idempotencyKey: attempt.key })
      }
      if (payment.status === 'success' && ['paid', 'shipped', 'completed'].includes(payment.order_status)) {
        this.setData({ notice: '模拟支付成功' })
      } else if (payment.status === 'failed') {
        this.setData({ notice: '本次模拟支付失败，可重新创建支付尝试' })
      } else {
        throw { message: '支付结果待确认，请重试查询原支付。' }
      }
      wx.removeStorageSync(storage)
      this.setData({ pendingPayment: false })
      await this.load()
    } catch (error) {
      if ([400, 403, 404, 409].includes(error.status) && error.code !== 10009) {
        wx.removeStorageSync(storage)
        wx.removeStorageSync(createKey)
        this.setData({ pendingPayment: false })
        await this.load()
      }
      this.setData({ error: error.message || '支付结果待确认，请重试查询原支付。' })
    } finally { this.setData({ busy: false }) }
  },
  cancel() { this.command(`/orders/${this.data.no}/cancel/`, `siq.mini.cancel.${this.data.no}`, { reason: 'user_changed_mind' }) },
  receive() { this.command(`/orders/${this.data.no}/receive/`, `siq.mini.receive.${this.data.no}`) },
  unavailable() { wx.showToast({ title: '订阅模板未配置，站内消息仍可用', icon: 'none' }) },
})
