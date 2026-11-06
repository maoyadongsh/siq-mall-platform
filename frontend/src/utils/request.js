import axios from 'axios'
import { ElMessage } from 'element-plus'

import { useUserStore } from '@/stores/user'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const service = axios.create({ baseURL, timeout: 15000 })

let refreshingPromise = null

service.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.accessToken) {
    config.headers.Authorization = `Bearer ${userStore.accessToken}`
  }
  return config
})

service.interceptors.response.use(
  (response) => {
    // 后端统一结构：code=0 时把 data 直接交给调用方
    const body = response.data
    if (body && body.code === 0) {
      return body.data
    }
    const message = body?.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(Object.assign(new Error(message), { code: body?.code, body }))
  },
  async (error) => {
    const { response, config = {} } = error
    const body = response?.data

    // access 过期：用 refresh 换一次新 access 后重放原请求，只重试一次
    if (response?.status === 401 && !config._retried) {
      const userStore = useUserStore()
      if (!userStore.refreshToken) {
        userStore.clear()
        ElMessage.error(body?.message || '登录已过期，请重新登录')
        return Promise.reject(error)
      }
      try {
        if (!refreshingPromise) {
          refreshingPromise = userStore.refreshAccessToken().finally(() => {
            refreshingPromise = null
          })
        }
        const access = await refreshingPromise
        config._retried = true
        config.headers = { ...config.headers, Authorization: `Bearer ${access}` }
        return service(config)
      } catch (refreshError) {
        userStore.clear()
        ElMessage.error('登录已过期，请重新登录')
        return Promise.reject(refreshError)
      }
    }

    const message =
      body?.message ||
      (error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '网络异常，请确认后端服务已启动')
    if (!config.skipErrorMessage) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)

export default service
