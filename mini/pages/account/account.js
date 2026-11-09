const { request, isLoggedIn, logout } = require('../../utils/api')
Page({
  data: { profile: null, logged: false, error: '' },
  onShow() { this.load() },
  async load() {
    this.setData({ logged: isLoggedIn(), error: '' })
    if (!isLoggedIn()) return
    try {
      const profile = await request({ path: '/users/me/' })
      this.setData({ profile })
    } catch (error) {
      this.setData({ error: error.message })
    }
  },
  async signOut() {
    await logout()
    this.setData({ profile: null, logged: false })
  },
})
