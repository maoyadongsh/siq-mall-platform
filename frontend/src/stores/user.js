import axios from 'axios'
import { defineStore } from 'pinia'

import { login, register } from '@/api/auth'
import { ensureCsrfToken } from '@/utils/csrf'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const LOCK_KEY = 'mall_session_refresh_lock'
const LOGOUT_KEY = 'mall_session_logout_at'

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function withRefreshLock(task) {
  if (navigator.locks) {
    return navigator.locks.request('mall_session_refresh', task)
  }
  const owner = crypto.randomUUID()
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const lock = JSON.parse(localStorage.getItem(LOCK_KEY) || 'null')
    if (!lock || lock.expiresAt < Date.now()) {
      localStorage.setItem(LOCK_KEY, JSON.stringify({ owner, expiresAt: Date.now() + 10000 }))
      await delay(50)
      const confirmed = JSON.parse(localStorage.getItem(LOCK_KEY) || 'null')
      if (confirmed?.owner === owner) {
        try {
          return await task()
        } finally {
          if (JSON.parse(localStorage.getItem(LOCK_KEY) || 'null')?.owner === owner) {
            localStorage.removeItem(LOCK_KEY)
          }
        }
      }
    }
    await delay(100)
  }
  throw new Error('会话刷新繁忙，请稍后重试')
}

export const useUserStore = defineStore('user', {
  state: () => ({
    accessToken: '',
    profile: null,
    hasRefreshSession: true,
    restoreAttempted: false,
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken),
  },

  actions: {
    applySession(data) {
      this.accessToken = data.access
      this.profile = data.user
      this.hasRefreshSession = true
      sessionStorage.removeItem('mall_access_token')
      localStorage.removeItem('mall_refresh_token')
    },

    clear() {
      this.accessToken = ''
      this.profile = null
      this.hasRefreshSession = false
      sessionStorage.removeItem('mall_access_token')
      localStorage.removeItem('mall_refresh_token')
    },

    async login(credentials) {
      const data = await login(credentials)
      this.applySession(data)
      return data
    },

    async register(payload) {
      const data = await register(payload)
      this.applySession(data)
      return data
    },

    async restoreSession() {
      if (this.restoreAttempted) return
      this.restoreAttempted = true
      if (!this.hasRefreshSession) return
      try {
        await this.refreshAccessToken()
      } catch {
        this.clear()
      }
    },

    async refreshAccessToken() {
      return withRefreshLock(async () => {
        const csrfToken = await ensureCsrfToken()
        const { data } = await axios.post(
          `${baseURL}/auth/web/refresh/`,
          {},
          {
            headers: { 'X-CSRF-Token': csrfToken },
            withCredentials: true,
            timeout: 15000,
          },
        )
        this.applySession(data.data)
        return this.accessToken
      })
    },
  },
})

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === LOGOUT_KEY) {
      useUserStore().clear()
    }
  })
}
