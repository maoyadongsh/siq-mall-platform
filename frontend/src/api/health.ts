import type { Schemas } from '@/types/models'
import request from '@/utils/request'

export type HealthData = Schemas['HealthData']

/**
 * 健康检查。
 * 依赖降级时后端返回 HTTP 503，但响应体仍是统一结构（code=0 + data.status=degraded），
 * 因此这里放开状态码校验，让页面能拿到 checks 明细。
 */
export function fetchHealth(): Promise<HealthData> {
  return request.get('/health/', {
    validateStatus: (status) => status === 200 || status === 503,
    skipErrorMessage: true,
  })
}
