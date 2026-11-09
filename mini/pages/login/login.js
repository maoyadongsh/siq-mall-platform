const { login } = require('../../utils/api')
Page({
  data: { identifier: '', password: '', busy: false, error: '' },
  onInput(event) { this.setData({ [event.currentTarget.dataset.field]: event.detail.value }) },
  async submit() {
    if (this.data.busy || !this.data.identifier || !this.data.password) return
    this.setData({ busy: true, error: '' })
    try {
      await login(this.data.identifier, this.data.password)
      const pages = getCurrentPages()
      if (pages.length > 1) wx.navigateBack()
      else wx.switchTab({ url: '/pages/index/index' })
    } catch (error) {
      this.setData({ error: error.message, busy: false })
    }
  },
  unavailable() {
    wx.showToast({ title: '微信平台登录待AppID配置', icon: 'none' })
  },
})
