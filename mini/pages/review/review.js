const { request, uuid } = require('../../utils/api')
Page({
  data: { no: '', rows: [], loading: true, error: '', notice: '' },
  onLoad(options) { this.setData({ no: options.no }) },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [order, reviews] = await Promise.all([
        request({ path: `/orders/${this.data.no}/` }),
        request({ path: `/users/me/reviews/?order_no=${this.data.no}` }),
      ])
      const byItem = new Map(reviews.results.map((row) => [row.order_item_id, row]))
      this.setData({ rows: order.items.map((item) => ({ ...item, rating: 5, content: '', review: byItem.get(item.order_item_id) })), loading: false })
    } catch (error) { this.setData({ error: error.message, loading: false }) }
  },
  onRating(event) {
    const { index, value } = event.currentTarget.dataset
    this.setData({ [`rows[${index}].rating`]: Number(value) })
  },
  onContent(event) {
    this.setData({ [`rows[${event.currentTarget.dataset.index}].content`]: event.detail.value })
  },
  async submit(event) {
    const index = event.currentTarget.dataset.index
    const item = this.data.rows[index]
    if (!item.content.trim() || item.review) return
    const storage = `siq.mini.review.${item.order_item_id}`
    const key = wx.getStorageSync(storage) || uuid()
    wx.setStorageSync(storage, key)
    this.setData({ error: '', notice: '' })
    try {
      await request({ path: '/reviews/', method: 'POST', data: { order_item_id: Number(item.order_item_id), rating: item.rating, content: item.content.trim() }, idempotencyKey: key })
      wx.removeStorageSync(storage)
      this.setData({ notice: '评价已提交，等待审核', content: '' })
      await this.load()
    } catch (error) {
      if ([400, 403, 404, 409].includes(error.status)) wx.removeStorageSync(storage)
      this.setData({ error: error.message })
    }
  },
})
