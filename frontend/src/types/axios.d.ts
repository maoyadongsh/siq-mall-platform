import 'axios'

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipErrorMessage?: boolean
    _retried?: boolean
  }
}
