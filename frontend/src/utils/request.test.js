import { AxiosError } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { messageError, userStore } = vi.hoisted(() => ({
  messageError: vi.fn(),
  userStore: {
    accessToken: '',
    refreshToken: '',
    clear: vi.fn(),
    refreshAccessToken: vi.fn(),
  },
}))

vi.mock('@/stores/user', () => ({ useUserStore: () => userStore }))
vi.mock('element-plus', () => ({ ElMessage: { error: messageError } }))

import service from './request'

function makeResponse(config, status, data) {
  return { data, status, statusText: '', headers: {}, config }
}

function unauthorized(config) {
  const response = makeResponse(config, 401, { code: 10002, message: '登录已过期' })
  return new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, {}, response)
}

describe('request 401 handling', () => {
  beforeEach(() => {
    userStore.accessToken = 'expired-access'
    userStore.refreshToken = 'refresh-token'
    userStore.clear.mockReset()
    userStore.refreshAccessToken.mockReset()
    messageError.mockReset()
  })

  it('shares one refresh across concurrent requests and replays them once', async () => {
    const requests = []
    let releaseRefresh
    userStore.refreshAccessToken.mockImplementation(
      () =>
        new Promise((resolve) => {
          releaseRefresh = () => {
            userStore.accessToken = 'new-access'
            resolve('new-access')
          }
        }),
    )
    service.defaults.adapter = async (config) => {
      requests.push(config.headers.Authorization)
      if (config.headers.Authorization === 'Bearer expired-access') {
        throw unauthorized(config)
      }
      return makeResponse(config, 200, { code: 0, data: { url: config.url } })
    }

    const pending = Promise.all([service.get('/first'), service.get('/second')])
    await vi.waitFor(() => {
      expect(requests).toHaveLength(2)
      expect(userStore.refreshAccessToken).toHaveBeenCalledTimes(1)
    })
    releaseRefresh()

    await expect(pending).resolves.toEqual([{ url: '/first' }, { url: '/second' }])
    expect(requests).toEqual([
      'Bearer expired-access',
      'Bearer expired-access',
      'Bearer new-access',
      'Bearer new-access',
    ])
  })

  it('clears the session and does not replay when refresh fails', async () => {
    const requests = []
    userStore.refreshAccessToken.mockRejectedValue(new Error('refresh failed'))
    service.defaults.adapter = async (config) => {
      requests.push(config)
      throw unauthorized(config)
    }

    await expect(service.get('/protected')).rejects.toThrow('refresh failed')
    expect(userStore.clear).toHaveBeenCalledTimes(1)
    expect(requests).toHaveLength(1)
  })

  it('clears the session without calling refresh when no refresh token exists', async () => {
    userStore.refreshToken = ''
    service.defaults.adapter = async (config) => {
      throw unauthorized(config)
    }

    await expect(service.get('/protected')).rejects.toThrow('Unauthorized')
    expect(userStore.clear).toHaveBeenCalledTimes(1)
    expect(userStore.refreshAccessToken).not.toHaveBeenCalled()
  })

  it.each(['post', 'patch', 'delete'])(
    'does not refresh or replay a %s request',
    async (method) => {
      const requests = []
      service.defaults.adapter = async (config) => {
        requests.push(config)
        throw unauthorized(config)
      }

      await expect(service[method]('/write', {})).rejects.toThrow('登录已过期')
      expect(requests).toHaveLength(1)
      expect(userStore.refreshAccessToken).not.toHaveBeenCalled()
      expect(userStore.clear).not.toHaveBeenCalled()
    },
  )

  it('does not replay again when the refreshed access is still rejected', async () => {
    const requests = []
    userStore.refreshAccessToken.mockResolvedValue('still-invalid-access')
    service.defaults.adapter = async (config) => {
      requests.push(config)
      throw unauthorized(config)
    }

    await expect(service.get('/protected')).rejects.toThrow('登录已过期')
    expect(requests).toHaveLength(2)
    expect(userStore.refreshAccessToken).toHaveBeenCalledTimes(1)
  })

  it('returns a readable network error even when toast messages are disabled', async () => {
    service.defaults.adapter = async (config) => {
      const response = makeResponse(config, 500, '')
      throw new AxiosError(
        'Request failed with status code 500',
        'ERR_BAD_RESPONSE',
        config,
        {},
        response,
      )
    }

    await expect(service.get('/health/', { skipErrorMessage: true })).rejects.toThrow(
      '网络异常，请确认后端服务已启动',
    )
    expect(messageError).not.toHaveBeenCalled()
  })
})
