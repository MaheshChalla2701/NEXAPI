import type { AnalystAnswer, MetaResponse, Suggestion } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code?: string

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { ...init, headers: { Accept: 'application/json', ...init?.headers } })
  } catch {
    throw new ApiError(0, 'Cannot reach the API server.', 'unreachable')
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // non-JSON body (e.g. proxy error page); handled below
  }
  if (!res.ok) {
    const b = (body ?? {}) as { error?: string; code?: string }
    const code = b.code ?? (res.status === 502 || res.status === 504 ? 'unreachable' : undefined)
    throw new ApiError(res.status, b.error ?? `Request failed with status ${res.status}`, code)
  }
  return body as T
}

export const api = {
  meta: () => request<MetaResponse>('/api/meta'),
  suggestions: () => request<{ suggestions: Suggestion[] }>('/api/analyst/suggestions'),
  ask: (question: string, mode: 'auto' | 'local' | 'external') =>
    request<AnalystAnswer>('/api/analyst/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, mode }),
    }),
}
