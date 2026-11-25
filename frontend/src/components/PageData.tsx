import type { ReactNode } from 'react'
import type { Envelope, Meta } from '../api/types'
import { useApi } from '../lib/hooks'
import { ErrorState, LoadingState } from './ui/States'

/** Loads one page endpoint and handles the loading / error states uniformly. */
export function PageData<T>({ path, children }: { path: string; children: (data: T, meta: Meta) => ReactNode }) {
  const { data, error, loading, reload } = useApi<Envelope<T>>(path)
  if (!data && loading) return <LoadingState />
  if (!data && error) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null
  return <div className={`page-body ${loading ? 'is-refreshing' : ''}`}>{children(data.data, data.meta)}</div>
}
