import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
let csrfPromise: Promise<string> | null = null

export function readCookie(name: string): string {
  const item = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.slice(name.length + 1)) : ''
}

export function hasCookie(name: string): boolean {
  return Boolean(readCookie(name))
}

export async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie('mall_csrf')
  if (existing) return existing
  if (!csrfPromise) {
    csrfPromise = axios
      .get<{ data?: { csrf_token?: string } }>(`${baseURL}/auth/csrf/`, {
        withCredentials: true,
        timeout: 15000,
      })
      .then((response) => response.data?.data?.csrf_token || '')
      .finally(() => {
        csrfPromise = null
      })
  }
  const token = await csrfPromise
  if (!token) throw new Error('无法建立安全校验，请稍后重试')
  return token
}
