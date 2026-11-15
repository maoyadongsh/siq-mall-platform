export function messageOf(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return String((error as { message: unknown }).message)
  }
  return String(error)
}

export function statusOf(error: unknown): number | undefined {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { status?: number } }).response
    return response?.status
  }
  return undefined
}

export function codeOf(error: unknown): number | undefined {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { code?: number } } }).response
    return response?.data?.code
  }
  return undefined
}
