import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { ApiError, request } from '../api/client'

interface ApiState<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
}

/** Fetch a JSON endpoint. On refetch the previous data stays on screen. */
export function useApi<T>(path: string | null) {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: path !== null })
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!path) return
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null }))
    request<T>(path)
      .then((data) => !cancelled && setState({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (cancelled) return
        const error = e instanceof ApiError ? e : new ApiError(0, String(e))
        setState((s) => ({ data: s.data, error, loading: false }))
      })
    return () => {
      cancelled = true
    }
  }, [path, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { ...state, reload }
}

/** Width of an element, kept current with ResizeObserver. */
export function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setWidth(el.clientWidth)
    const ro = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

/** useId, made safe for use inside SVG url(#id) references. */
export function useSvgId(prefix: string): string {
  return `${prefix}-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
}
