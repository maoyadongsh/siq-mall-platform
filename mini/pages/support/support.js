const { request, uuid } = require('../../utils/api')
Page({
  data: { conversation: null, rows: [], pending: [], draft: '', pollCursor: null, loading: true, error: '', busy: false },
  onShow() {
    this.load()
    this.timer = setInterval(() => this.poll(), 5000)
  },
  onHide() { clearInterval(this.timer) },
  onUnload() { clearInterval(this.timer) },
  async create() {
    this.setData({ busy: true, error: '' })
    try {
      const key = wx.getStorageSync('siq.mini.support.create') || uuid()
      wx.setStorageSync('siq.mini.support.create', key)
      const conversation = await request({ path: '/conversations/', method: 'POST', data: {}, idempotencyKey: key })
      wx.removeStorageSync('siq.mini.support.create')
      this.setData({ conversation, rows: [], pending: [], pollCursor: null, busy: false })
      await this.loadMessages()
    } catch (error) { this.setData({ error: error.message, busy: false }) }
  },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const data = await request({ path: '/conversations/?page_size=20' })
      const active = data.results.find((row) => row.status === 'open') || data.results[0]
      if (active) {
        this.setData({ conversation: active })
        await this.loadMessages()
      } else this.setData({ loading: false })
    } catch (error) { this.setData({ error: error.message, loading: false }) }
  },
  async loadMessages() {
    if (!this.data.conversation) return
    const data = await request({ path: `/conversations/${this.data.conversation.id}/messages/?direction=older&limit=50` })
    this.setData({ rows: data.results, pollCursor: data.poll_cursor, loading: false })
    await this.markRead()
  },
  async poll() {
    if (!this.data.conversation || this.data.conversation.status !== 'open') return
    try {
      if (!this.data.pollCursor) {
        await this.loadMessages()
        return
      }
      const data = await request({ path: `/conversations/${this.data.conversation.id}/messages/?direction=newer&cursor=${encodeURIComponent(this.data.pollCursor)}` })
      if (data.results.length) {
        const known = new Set(this.data.rows.map((row) => row.id))
        this.setData({ rows: this.data.rows.concat(data.results.filter((row) => !known.has(row.id))), pollCursor: data.poll_cursor || data.next_cursor })
        await this.markRead()
      }
    } catch (error) { return }
  },
  async markRead() {
    const latest = this.data.rows[this.data.rows.length - 1]
    if (latest) await request({ path: `/conversations/${this.data.conversation.id}/read/`, method: 'POST', data: { last_message_id: Number(latest.id) } })
  },
  onInput(event) { this.setData({ draft: event.detail.value }) },
  async send(event) {
    const item = event ? event.currentTarget.dataset.item : { client_message_id: uuid(), body: this.data.draft.trim(), state: 'sending' }
    if (!item.body || this.data.conversation.status !== 'open') return
    item.state = event ? 'retrying' : 'sending'
    if (!event) this.setData({ pending: this.data.pending.concat(item) })
    else this.setData({ pending: [...this.data.pending] })
    this.setData({ error: '' })
    try {
      const row = await request({ path: `/conversations/${this.data.conversation.id}/messages/`, method: 'POST', data: { client_message_id: item.client_message_id, body: item.body }, idempotencyKey: item.client_message_id })
      this.setData({ rows: this.data.rows.concat(row), pending: this.data.pending.filter((pending) => pending.client_message_id !== item.client_message_id), draft: '' })
      await this.loadMessages()
    } catch (error) {
      item.state = 'failed'
      this.setData({ pending: [...this.data.pending], error: `${error.message}；可用原消息标识重试。` })
    }
  },
  async close() {
    const row = this.data.conversation
    try {
      const key = wx.getStorageSync(`siq.mini.support.close.${row.id}`) || uuid()
      wx.setStorageSync(`siq.mini.support.close.${row.id}`, key)
      await request({ path: `/conversations/${row.id}/close/`, method: 'POST', data: { reason: '结束咨询' }, idempotencyKey: key })
      wx.removeStorageSync(`siq.mini.support.close.${row.id}`)
      this.setData({ conversation: { ...row, status: 'closed' } })
    } catch (error) { this.setData({ error: error.message }) }
  },
})
