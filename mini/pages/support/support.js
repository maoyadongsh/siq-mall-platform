const { request, uuid } = require('../../utils/api')

function socketBase() {
  const url = getApp().globalData.apiBaseUrl.replace(/^http/, 'ws')
  const index = url.indexOf('/api/')
  return index > -1 ? url.slice(0, index) : url
}

Page({
  data: {
    conversation: null,
    rows: [],
    pending: [],
    draft: '',
    pollCursor: null,
    loading: true,
    error: '',
    busy: false,
    socketState: 'off',
  },
  onShow() {
    this.closedByUs = false
    this.load().then(() => this.startRealtime())
    this.startPolling()
  },
  onHide() { this.stopRealtime(); clearInterval(this.timer) },
  onUnload() { this.stopRealtime(); clearInterval(this.timer) },
  async create() {
    this.setData({ busy: true, error: '' })
    try {
      const key = wx.getStorageSync('siq.mini.support.create') || uuid()
      wx.setStorageSync('siq.mini.support.create', key)
      const conversation = await request({ path: '/conversations/', method: 'POST', data: {}, idempotencyKey: key })
      wx.removeStorageSync('siq.mini.support.create')
      this.setData({ conversation, rows: [], pending: [], pollCursor: null, busy: false })
      await this.loadMessages()
      this.restartRealtime()
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
  startPolling(ms = 5000) {
    clearInterval(this.timer)
    this.timer = setInterval(() => this.poll(), ms)
  },
  startRealtime() {
    this.closedByUs = false
    this.attempts = 0
    return this.connectSocket()
  },
  restartRealtime() {
    this.stopRealtime()
    return this.startRealtime()
  },
  stopRealtime() {
    this.closedByUs = true
    clearTimeout(this.reconnectTimer)
    clearInterval(this.heartbeatTimer)
    if (this.socketTask) {
      const task = this.socketTask
      this.socketTask = null
      task.close({ code: 1000 })
    }
    this.setData({ socketState: 'off' })
  },
  scheduleReconnect() {
    if (this.closedByUs || !this.data.conversation || this.data.conversation.status !== 'open') return
    if (this.attempts >= 5) return
    const delay = Math.min(1000 * Math.pow(2, this.attempts), 30000)
    this.attempts += 1
    clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => this.connectSocket(), delay)
  },
  startHeartbeat() {
    clearInterval(this.heartbeatTimer)
    this.lastSocketAt = Date.now()
    this.heartbeatTimer = setInterval(() => {
      if (Date.now() - this.lastSocketAt > this.heartbeatMs * 2) {
        if (this.socketTask) this.socketTask.close({ code: 4000 })
        return
      }
      if (this.socketTask) this.socketTask.send({ data: JSON.stringify({ type: 'ping' }) })
    }, this.heartbeatMs)
  },
  async connectSocket() {
    if (this.closedByUs || this.socketTask || this.data.socketState === 'connecting') return
    if (!this.data.conversation || this.data.conversation.status !== 'open') return
    this.setData({ socketState: 'connecting' })
    try {
      const ticket = await request({
        path: '/conversations/ws-ticket/',
        method: 'POST',
        data: { conversation_id: Number(this.data.conversation.id) },
      })
      if (this.closedByUs) { this.setData({ socketState: 'off' }); return }
      this.heartbeatMs = ticket.heartbeat_seconds * 1000
      const task = wx.connectSocket({
        url: `${socketBase()}${ticket.path}`,
        protocols: [`support.ticket.${ticket.ticket}`],
      })
      this.socketTask = task
      task.onOpen(() => {
        if (this.socketTask !== task) return
        this.attempts = 0
        this.setData({ socketState: 'open' })
        this.startHeartbeat()
        this.startPolling()
      })
      task.onMessage((event) => {
        if (this.socketTask !== task) return
        this.lastSocketAt = Date.now()
        let payload
        try { payload = JSON.parse(event.data) } catch (error) { return }
        this.handleSocketMessage(payload)
      })
      task.onError(() => { if (this.socketTask === task) task.close({ code: 4001 }) })
      task.onClose(() => {
        if (this.socketTask !== task) return
        this.socketTask = null
        clearInterval(this.heartbeatTimer)
        if (this.closedByUs) return
        this.setData({ socketState: 'waiting' })
        this.startPolling()
        this.scheduleReconnect()
      })
    } catch (error) {
      this.setData({ socketState: 'off' })
      this.scheduleReconnect()
    }
  },
  handleSocketMessage(payload) {
    if (payload.type === 'message' && payload.message) {
      const row = payload.message
      const rows = this.data.rows.some((existing) => existing.id === row.id)
        ? this.data.rows
        : this.data.rows.concat(row)
      this.setData({ rows })
      this.markRead().catch(() => undefined)
      return
    }
    if (payload.type === 'closed') {
      this.setData({ conversation: { ...this.data.conversation, status: 'closed' } })
      this.stopRealtime()
    }
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
      this.stopRealtime()
    } catch (error) { this.setData({ error: error.message }) }
  },
})
