const KEYS = {
  access: 'siq.mini.access',
  refresh: 'siq.mini.refresh',
  session: 'siq.mini.session',
  user: 'siq.mini.user',
}
let refreshPromise = null

function baseUrl() {
  return getApp().globalData.apiBaseUrl
}
function store(key, value) {
  if (value === null || value === undefined || value === '') wx.removeStorageSync(key)
  else wx.setStorageSync(key, value)
}
function clearSession() {
  Object.values(KEYS).forEach((key) => store(key, null))
}
function saveSession(data) {
  store(KEYS.access, data.access)
  store(KEYS.refresh, data.refresh)
  store(KEYS.session, data.session_id)
  store(KEYS.user, data.user)
}
function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16)
    return (char === 'x' ? value : (value & 3) | 8).toString(16)
  })
}
function rawRequest(options) {
  return new Promise((resolve, reject) => {
    const access = wx.getStorageSync(KEYS.access)
    wx.request({
      url: baseUrl() + options.path,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(access && options.auth !== false ? { Authorization: `Bearer ${access}` } : {}),
        ...(options.idempotencyKey ? { 'Idempotency-Key': options.idempotencyKey } : {}),
      },
      success: (response) => {
        const body = response.data || {}
        if (response.statusCode >= 200 && response.statusCode < 300 && body.code === 0) resolve(body.data)
        else reject({ status: response.statusCode, code: body.code, message: body.message || '请求失败' })
      },
      fail: () => reject({ type: 'network', message: '网络异常，请检查连接后重试' }),
    })
  })
}
function refreshSession() {
  if (!refreshPromise) {
    const refresh = wx.getStorageSync(KEYS.refresh)
    refreshPromise = rawRequest({ path: '/auth/mini/refresh/', method: 'POST', data: { refresh }, auth: false })
      .then(saveSession)
      .catch((error) => {
        clearSession()
        throw error
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}
async function request(options) {
  try {
    return await rawRequest(options)
  } catch (error) {
    if (error.status !== 401 || options._retried || options.auth === false) throw error
    if (!wx.getStorageSync(KEYS.refresh)) {
      clearSession()
      throw error
    }
    await refreshSession()
    if (!['GET', 'HEAD', 'OPTIONS'].includes((options.method || 'GET').toUpperCase())) throw error
    return rawRequest({ ...options, _retried: true })
  }
}
async function login(identifier, password) {
  const data = await rawRequest({ path: '/auth/mini/login/', method: 'POST', data: { identifier, password }, auth: false })
  saveSession(data)
  return data
}
async function logout() {
  try {
    await request({ path: '/auth/mini/logout/', method: 'POST', data: {} })
  } finally {
    clearSession()
  }
}
function isLoggedIn() {
  return Boolean(wx.getStorageSync(KEYS.refresh))
}
module.exports = { request, login, logout, refreshSession, isLoggedIn, clearSession, uuid, KEYS }
