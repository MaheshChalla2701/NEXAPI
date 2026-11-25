import type { Unit } from '../api/types'

// Display formatting only. Values arrive fully computed from the API.

let currency = 'USD'
export function setCurrency(code: string | undefined) {
  currency = code || 'USD'
}

const MINUS = '−'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export type FormatUnit = Unit | 'currency_diff'

function signed(v: number, body: string): string {
  if (v > 0) return `+${body}`
  if (v < 0) return `${MINUS}${body}`
  return body
}

function money(v: number, compact = false): string {
  const abs = Math.abs(v)
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      notation: compact ? 'compact' : 'standard',
      minimumFractionDigits: compact || abs >= 1000 ? 0 : 2,
      maximumFractionDigits: compact ? 1 : abs >= 1000 ? 0 : 2,
    })
      .format(v)
      .replace('-', MINUS)
  } catch {
    return `${currency} ${v.toFixed(2)}`
  }
}

export function fmt(
  v: number | null | undefined,
  unit: FormatUnit,
  opts: { compact?: boolean; digits?: number } = {},
): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const d = opts.digits
  switch (unit) {
    case 'currency':
      return money(v, opts.compact)
    case 'currency_diff':
      return signed(v, money(Math.abs(v), opts.compact))
    case 'rate':
      return `${(v * 100).toFixed(d ?? 1)}%`
    case 'rate_diff':
      return signed(v, `${Math.abs(v * 100).toFixed(d ?? 1)} pp`)
    case 'pct':
      return signed(v, `${Math.abs(v).toFixed(d ?? 1)}%`)
    case 'pp':
      return signed(v, `${Math.abs(v).toFixed(d ?? 2)} pp`)
    case 'count':
      return opts.compact && Math.abs(v) >= 10000
        ? new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(v)
        : Math.round(v).toLocaleString('en-US')
  }
}

/** Axis tick label: decimals follow the tick step so labels stay clean. */
export function fmtTick(v: number, unit: FormatUnit, step: number): string {
  const decimals = (s: number) => Math.max(0, Math.min(3, -Math.floor(Math.log10(s) + 1e-9)))
  switch (unit) {
    case 'rate':
      return `${(v * 100).toFixed(decimals(step * 100))}%`
    case 'rate_diff':
      return v === 0 ? '0' : signed(v, Math.abs(v * 100).toFixed(decimals(step * 100)))
    case 'pct':
    case 'pp':
      return v === 0 ? '0' : signed(v, Math.abs(v).toFixed(decimals(step)))
    case 'currency':
    case 'currency_diff':
      return money(v, Math.abs(v) >= 10000)
    case 'count':
      return fmt(v, 'count', { compact: true })
  }
}

export function monthLabel(ym: string, withYear = false): string {
  const [y, m] = ym.split('-')
  const name = MONTHS[Number(m) - 1] ?? ym
  return withYear ? `${name} ${y}` : name
}

export function dayLabel(iso: string, withYear = false): string {
  const [y, m, d] = iso.split('-')
  const base = `${Number(d)} ${MONTHS[Number(m) - 1] ?? ''}`
  return withYear ? `${base} ${y}` : base
}

export function periodLabel(period: string | undefined): string {
  if (!period) return ''
  const [from, to] = period.split(' to ')
  return to ? `${dayLabel(from)} – ${dayLabel(to, true)}` : period
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}
