const { request } = require('../../utils/api')
Page({
  data: { kind: '', id: '', content: null, loading: true, error: '' },
  onLoad(options) { this.setData({ kind: options.kind, id: options.id }); this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const kind = this.data.kind === 'page' ? 'pages' : 'announcements'
      const content = await request({ path: `/cms/${kind}/${this.data.id}/?platform=mini`, auth: false })
      this.setData({ content, loading: false })
    } catch (error) {
      this.setData({ error: '内容不存在、尚未发布或已下线', loading: false })
    }
  },
  navigate(event) {
    const url = event.currentTarget.dataset.url
    const product = url.match(/^\/products\/(\d+)\/?$/)
    const page = url.match(/^\/pages\/([a-z0-9-]+)\/?$/)
    const announcement = url.match(/^\/announcements\/(\d+)\/?$/)
    if (product) wx.navigateTo({ url: `/pages/product/product?id=${product[1]}` })
    else if (page) wx.navigateTo({ url: `/pages/content/content?kind=page&id=${page[1]}` })
    else if (announcement) wx.navigateTo({ url: `/pages/content/content?kind=announcement&id=${announcement[1]}` })
    else if (url === '/') wx.switchTab({ url: '/pages/index/index' })
    else wx.showToast({ title: '此站内链接暂不支持打开', icon: 'none' })
  },
  copyLink(event) {
    wx.setClipboardData({ data: event.currentTarget.dataset.url })
  },
})
