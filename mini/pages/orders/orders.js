const { request } = require('../../utils/api')
Page({
  data: { rows: [], loading: true, error: '' },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const data = await request({ path: '/orders/?page_size=50' })
      this.setData({ rows: data.results, loading: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
})
