import type { CheckStatus, Confidence, Recommendation } from '../../api/types'
import { Icon, type IconName } from './Icon'

// Status colour never carries meaning alone: every badge has an icon and a label.

export function SourceBadge({ isMock }: { isMock: boolean }) {
  if (isMock) return null
  return (
    <span className="badge badge-good">
      <Icon name="database" size={13} /> Assignment data
    </span>
  )
}

const REC: Record<Recommendation, { cls: string; icon: IconName; label: string }> = {
  KEEP: { cls: 'badge-good', icon: 'check', label: 'Keep' },
  CHANGE: { cls: 'badge-warning', icon: 'refresh', label: 'Change' },
  STOP: { cls: 'badge-critical', icon: 'x', label: 'Stop' },
  PENDING: { cls: 'badge-neutral', icon: 'clock', label: 'Pending analysis' },
}

export function RecommendationBadge({ value }: { value: Recommendation }) {
  const r = REC[value]
  return (
    <span className={`badge ${r.cls}`}>
      <Icon name={r.icon} size={13} /> {r.label}
    </span>
  )
}

export function ConfidenceBadge({ value, isMock }: { value: Confidence | null; isMock?: boolean }) {
  if (isMock) return <span className="badge badge-outline" title="Confidence is not meaningful for mock data">Mock</span>
  if (!value) return <span className="badge badge-outline">Not assessed</span>
  const filled = { high: 3, medium: 2, low: 1 }[value]
  return (
    <span className="badge badge-outline" aria-label={`${value} confidence`}>
      <span className="conf-dots" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span key={i} className={i <= filled ? 'on' : ''} />
        ))}
      </span>
      {value.charAt(0).toUpperCase() + value.slice(1)}
    </span>
  )
}

const STATUS: Record<CheckStatus, { cls: string; icon: IconName; label: string }> = {
  pass: { cls: 'badge-good', icon: 'check', label: 'Pass' },
  warn: { cls: 'badge-warning', icon: 'alert', label: 'Warning' },
  fail: { cls: 'badge-critical', icon: 'x', label: 'Fail' },
  pending: { cls: 'badge-neutral', icon: 'clock', label: 'Pending' },
}

export function StatusBadge({ value }: { value: CheckStatus }) {
  const s = STATUS[value]
  return (
    <span className={`badge ${s.cls}`}>
      <Icon name={s.icon} size={13} /> {s.label}
    </span>
  )
}

const MATCH: Record<'match' | 'mismatch' | 'pending', CheckStatus> = { match: 'pass', mismatch: 'fail', pending: 'pending' }
export function MatchBadge({ value }: { value: 'match' | 'mismatch' | 'pending' }) {
  const s = STATUS[MATCH[value]]
  const label = { match: 'Match', mismatch: 'Mismatch', pending: 'Pending' }[value]
  return (
    <span className={`badge ${s.cls}`}>
      <Icon name={s.icon} size={13} /> {label}
    </span>
  )
}
