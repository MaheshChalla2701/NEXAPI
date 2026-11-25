import { useEffect, useState } from 'react'

// Minimal hash router: #/page?param=value. No dependency needed.

export interface Route {
  page: string
  params: URLSearchParams
}

function parse(): Route {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const [page, qs = ''] = raw.split('?')
  return { page: page || 'overview', params: new URLSearchParams(qs) }
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const onChange = () => setRoute(parse())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function href(page: string, params?: Record<string, string>): string {
  const qs = params ? `?${new URLSearchParams(params).toString()}` : ''
  return `#/${page}${qs}`
}

export function askAnalystHref(question: string): string {
  return href('analyst', { q: question })
}
