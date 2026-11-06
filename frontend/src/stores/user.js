import axios from 'axios'
import { defineStore } from 'pinia'

const ACCESS_KEY = 'mall_access_token'
const REFRESH_KEY = 'mall_refresh_token'
const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const useUserStore = defineStore('user', {
  state: () => ({
    accessToken: sessionStorage.getItem(ACCESS_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_KEY) || '',
    profile: null,
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken),
  },

  actions: {
    setTokens({ access, refresh }) {
      if (access) {
        this.accessToken = access
        sessionStorage.setItem(ACCESS_KEY, access)
      }
      if (refresh) {
        this.refreshToken = refresh
        localStorage.setItem(REFRESH_KEY, refresh)
      }
    },

    clear() {
      this.accessToken = ''
      this.refreshToken = ''
      this.profile = null
      sessionStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
    },

    /** 刷新 access：refresh 轮换后需同步保存新 refresh（架构文档 §5.5） */
    async refreshAccessToken() {
      const { data } = await axios.post(
        `${baseURL}/auth/refresh/`,
        { refresh: this.refreshToken },
        { timeout: 15000 },
      )
      const payload = data?.data || {}
      this.setTokens({ access: payload.access, refresh: payload.refresh })
      return this.accessToken
    },
  },
})
