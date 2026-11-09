const { request } = require('../../utils/api')
Page({
  data: { rows: [], form: { recipient: '', phone: '', province: '浙江省', city: '杭州市', district: '西湖区', detail: '', region_code: '330106' }, loading: true, error: '', notice: '', busy: false },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const rows = await request({ path: '/users/me/addresses/' })
      this.setData({ rows, loading: false })
    } catch (error) { this.setData({ error: error.message, loading: false }) }
  },
  onInput(event) {
    this.setData({ [`form.${event.currentTarget.dataset.field}`]: event.detail.value })
  },
  async submit() {
    if (this.data.busy) return
    this.setData({ busy: true, error: '', notice: '' })
    try {
      await request({ path: '/users/me/addresses/', method: 'POST', data: { ...this.data.form, is_default: !this.data.rows.length } })
      this.setData({ notice: '地址已保存', busy: false, form: { recipient: '', phone: '', province: '浙江省', city: '杭州市', district: '西湖区', detail: '', region_code: '330106' } })
      this.load()
    } catch (error) {
      this.setData({ error: error.message, busy: false })
    }
  },
  async makeDefault(event) {
    if (this.data.busy) return
    this.setData({ busy: true, error: '' })
    const row = event.currentTarget.dataset.item
    try {
      await request({ path: `/users/me/addresses/${row.id}/default/`, method: 'POST', data: {} })
      await this.load()
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ busy: false }) }
  },
  async remove(event) {
    const row = event.currentTarget.dataset.item
    try {
      await request({ path: `/users/me/addresses/${row.id}/`, method: 'DELETE', data: { expected_version: row.version } })
      this.load()
    } catch (error) { this.setData({ error: error.message }) }
  },
  unavailable() { wx.showToast({ title: '微信地址能力未配置，请手填', icon: 'none' }) },
})
