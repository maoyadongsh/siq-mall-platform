const { request, isLoggedIn } = require('../../utils/api')
const guest = require('../../utils/cart')
Page({
  data: { rows: [], loading: true, error: '', logged: false },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true, error: '', logged: isLoggedIn() })
    try {
      if (!isLoggedIn()) {
        this.setData({ rows: guest.read().items, loading: false })
        return
      }
      const profile = await request({ path: '/users/me/' })
      await guest.merge(profile.id)
      const data = await request({ path: '/carts/items/' })
      this.setData({ rows: data.items, loading: false })
    } catch (error) {
      this.setData({ error: error.message, loading: false })
    }
  },
  async update(event) {
    const item = event.currentTarget.dataset.item
    if (!this.data.logged) {
      guest.update(item.sku_id, event.detail.value)
      this.load()
      return
    }
    try {
      await request({ path: `/carts/items/${item.id}/`, method: 'PATCH', data: { quantity: Number(event.detail.value), expected_version: item.version } })
      this.load()
    } catch (error) {
      this.setData({ error: error.message })
      this.load()
    }
  },
  async remove(event) {
    const item = event.currentTarget.dataset.item
    if (!this.data.logged) {
      guest.remove(item.sku_id)
      this.load()
      return
    }
    try {
      await request({ path: `/carts/items/${item.id}/`, method: 'DELETE', data: { expected_version: item.version } })
      this.load()
    } catch (error) {
      this.setData({ error: error.message })
    }
  },
  checkout() {
    if (!isLoggedIn()) wx.navigateTo({ url: '/pages/login/login' })
    else wx.navigateTo({ url: '/pages/checkout/checkout' })
  },
})
