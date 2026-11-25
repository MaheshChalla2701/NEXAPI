import type { ReactNode } from 'react'
import type { ApiError } from '../../api/client'
import { Icon } from './Icon'

export function LoadingState({ label = 'Loading analysis…' }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="skeleton-grid" aria-hidden="true">
        <div className="skeleton" />
        <div className="skeleton" />
        <div className="skeleton" />
        <div className="skeleton tall" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const hint =
    error.code === 'unreachable' || error.status === 0
      ? 'Start the API from the repository root: python3 -m backend.server'
      : error.code === 'database_unavailable'
        ? 'Build the database first: python3 -m pipeline.build_db --source mock'
        : null
  return (
    <div className="state state-error" role="alert">
      <Icon name="alert" size={22} />
      <h3>Could not load this page</h3>
      <p>{error.message}</p>
      {hint && <code className="state-hint">{hint}</code>}
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          <Icon name="refresh" size={15} /> Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state-empty">
      <Icon name="info" size={20} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  )
}
