const { request } = require('../../utils/api')
Page({
  data: { rows: [], query: '', category: '', sort: 'newest', page: 1, totalPages: 1, loading: false, error: '' },
  onLoad(options) {
    this.setData({ query: options.q || '', category: options.category || '' })
    this.load()
  },
  async load(append = false) {
    if (this.data.loading) return
    this.setData({ loading: true, error: '' })
    try {
      const data = await request({ path: `/products/?q=${encodeURIComponent(this.data.query)}&category=${this.data.category}&sort=${this.data.sort}&page=${this.data.page}&page_size=20`, auth: false })
      const results = data.results.map((item) => ({
        ...item,
        display_price: Math.min(...item.skus.map((sku) => Number(sku.price))).toFixed(2),
      }))
      this.setData({ rows: append ? this.data.rows.concat(results) : results, totalPages: data.total_pages, loading: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  onQuery(event) { this.setData({ query: event.detail.value }) },
  onSearch() { this.setData({ page: 1 }); this.load() },
  onSort(event) { this.setData({ sort: event.currentTarget.dataset.value, page: 1 }); this.load() },
  onReachBottom() {
    if (this.data.page < this.data.totalPages) {
      this.setData({ page: this.data.page + 1 })
      this.load(true)
    }
  },
  onPullDownRefresh() { this.setData({ page: 1 }); this.load().finally(() => wx.stopPullDownRefresh()) },
})
