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
    if (this.data.busy || this.data.conversation?.status !== 'open') return
    const retry = event?.currentTarget?.dataset?.item
    const pending = this.data.pending
    const failed = retry && pending.find(row => row.client_message_id === retry.client_message_id && row.state === 'failed')
    if (retry && !failed) return
    const item = failed || { client_message_id: uuid(), body: this.data.draft.trim() }
    if (!item.body) return
    const sending = { ...item, state: 'sending' }
    this.setData({ busy: true, error: '', draft: failed ? this.data.draft : '', pending: failed
      ? pending.map(row => row === failed ? sending : row)
      : pending.concat(sending) })
    try {
      const row = await request({ path: `/conversations/${this.data.conversation.id}/messages/`, method: 'POST', data: { client_message_id: item.client_message_id, body: item.body }, idempotencyKey: item.client_message_id })
      const rows = this.data.rows.some(existing => existing.id === row.id) ? this.data.rows : this.data.rows.concat(row)
      this.setData({ rows, pending: this.data.pending.filter(p => p.client_message_id !== item.client_message_id) })
    } catch (error) {
      this.setData({ pending: this.data.pending.map(row => row.client_message_id === item.client_message_id ? { ...item, state: 'failed' } : row), error: `${error.message}；可用原消息标识重试。` })
      return
    } finally {
      this.setData({ busy: false })
    }
    try { await this.loadMessages() } catch (error) { this.setData({ error: error.message }) }
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
