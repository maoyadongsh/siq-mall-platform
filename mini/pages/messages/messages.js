const { request } = require('../../utils/api')
Page({
  data: { rows: [], watermark: '', cursor: null, hasMore: false, unread: 0, loading: true, error: '' },
  onShow() { this.load() },
  async load(append = false) {
    this.setData({ loading: true, error: '' })
    try {
      const [data, count] = await Promise.all([
        request({ path: `/notifications/?limit=20${append && this.data.cursor ? `&cursor=${encodeURIComponent(this.data.cursor)}` : ''}` }),
        request({ path: '/notifications/unread-count/' }),
      ])
      this.setData({ rows: append ? this.data.rows.concat(data.results) : data.results, watermark: data.read_watermark, cursor: data.next_cursor, hasMore: data.has_more, unread: count.total, loading: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  more() { if (this.data.hasMore) this.load(true) },
  async readAll() {
    try {
      await request({ path: '/notifications/read/', method: 'POST', data: { watermark: this.data.watermark } })
      this.load()
    } catch (error) { this.setData({ error: error.message }) }
  },
  async open(event) {
    const row = event.currentTarget.dataset.item
    try {
      if (!row.is_read) await request({ path: '/notifications/read/', method: 'POST', data: { ids: [Number(row.id)] } })
      const paths = { order: `/pages/order-detail/order-detail?no=${row.target_id}`, support: '/pages/support/support', announcement: `/pages/content/content?kind=announcement&id=${row.target_id}`, page: `/pages/content/content?kind=page&id=${row.target_id}` }
      if (paths[row.target_type]) wx.navigateTo({ url: paths[row.target_type] })
      else if (row.target_type === 'review') wx.navigateTo({ url: '/pages/orders/orders' })
      this.load()
    } catch (error) { this.setData({ error: error.message }) }
  },
})
