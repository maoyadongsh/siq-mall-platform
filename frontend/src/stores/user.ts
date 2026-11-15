import axios from 'axios'
import { defineStore } from 'pinia'

import { login as loginRequest, register as registerRequest, type LoginCredentials, type RegisterPayload } from '@/api/auth'
import type { SessionData, UserSummary } from '@/types/models'
import { ensureCsrfToken } from '@/utils/csrf'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const LOCK_KEY = 'mall_session_refresh_lock'
const LOGOUT_KEY = 'mall_session_logout_at'

let restorePending: Promise<string | void> | null = null

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function withRefreshLock<T>(task: () => Promise<T>): Promise<T> {
  if (navigator.locks) {
    return navigator.locks.request('mall_session_refresh', task)
  }
  const owner = crypto.randomUUID()
  for (let attempt = 0; attempt < 450; attempt += 1) {
    const lock = JSON.parse(localStorage.getItem(LOCK_KEY) || 'null') as {
      owner: string
      expiresAt: number
    } | null
    if (!lock || lock.expiresAt < Date.now()) {
      localStorage.setItem(LOCK_KEY, JSON.stringify({ owner, expiresAt: Date.now() + 40000 }))
      await delay(50)
      const confirmed = JSON.parse(localStorage.getItem(LOCK_KEY) || 'null') as {
        owner: string
      } | null
      if (confirmed?.owner === owner) {
        try {
          return await task()
        } finally {
          const current = JSON.parse(localStorage.getItem(LOCK_KEY) || 'null') as {
            owner: string
          } | null
          if (current?.owner === owner) {
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
    profile: null as UserSummary | null,
    hasRefreshSession: true,
    restoreAttempted: false,
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken),
  },

  actions: {
    applySession(data: SessionData) {
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

    async login(credentials: LoginCredentials): Promise<SessionData> {
      const data = await loginRequest(credentials)
      this.applySession(data)
      return data
    },

    async register(payload: RegisterPayload): Promise<SessionData> {
      const data = await registerRequest(payload)
      this.applySession(data)
      return data
    },

    async restoreSession(): Promise<string | void | undefined> {
      if (restorePending) return restorePending
      if (this.restoreAttempted) return
      this.restoreAttempted = true
      if (!this.hasRefreshSession) return
      restorePending = this.refreshAccessToken()
        .catch(() => this.clear())
        .finally(() => {
          restorePending = null
        })
      return restorePending
    },

    async refreshAccessToken(): Promise<string> {
      return withRefreshLock(async () => {
        const csrfToken = await ensureCsrfToken()
        const { data } = await axios.post<{ data: SessionData }>(
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
