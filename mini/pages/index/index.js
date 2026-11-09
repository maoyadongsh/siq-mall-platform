const { request } = require('../../utils/api')
Page({
  data: { loading: true, error: '', query: '', data: null, categories: [] },
  onLoad() { this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [data, categories] = await Promise.all([
        request({ path: '/cms/home/?platform=mini', auth: false }),
        request({ path: '/categories/tree/', auth: false }),
      ])
      this.setData({ data, categories, loading: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  onSearch() {
    wx.navigateTo({ url: `/pages/products/products?q=${encodeURIComponent(this.data.query)}` })
  },
  onQuery(event) { this.setData({ query: event.detail.value }) },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
})
