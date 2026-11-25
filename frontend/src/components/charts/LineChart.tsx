import { useState, type KeyboardEvent } from 'react'
import type { Row } from '../../api/types'
import { fmt, fmtTick, type FormatUnit } from '../../lib/format'
import { useWidth } from '../../lib/hooks'
import { linear, niceTicks } from '../../lib/scale'
import { TipRow, TipTitle, Tooltip } from './ChartFrame'

export interface Series {
  key: string
  label: string
  color: string
}

interface Props {
  rows: Row[]
  xKey: string
  series: Series[]
  unit: FormatUnit
  xLabel: (x: string) => string
  tipLabel?: (x: string) => string
  height?: number
  zeroBased?: boolean
  markers?: { x: string; label: string }[]
  band?: { from: string; to: string; label: string }
  ariaLabel: string
}

const M = { top: 16, bottom: 28, left: 56 }

/** Multi-series line chart with a snapping crosshair (pointer and arrow keys). */
export function LineChart({
  rows,
  xKey,
  series,
  unit,
  xLabel,
  tipLabel,
  height = 260,
  zeroBased = false,
  markers = [],
  band,
  ariaLabel,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [idx, setIdx] = useState<number | null>(null)
  const n = rows.length
  const value = (r: Row, k: string) => (typeof r[k] === 'number' ? (r[k] as number) : null)

  const all = rows.flatMap((r) => series.map((s) => value(r, s.key))).filter((v): v is number => v !== null)
  const lo = Math.min(...all, ...(zeroBased ? [0] : []))
  const hi = Math.max(...all, ...(zeroBased ? [0] : []))
  const pad = zeroBased ? 0 : (hi - lo) * 0.08
  const { ticks, step } = niceTicks(lo - pad, hi + pad, 5)
  const y = linear([ticks[0], ticks[ticks.length - 1]], [height - M.bottom, M.top])

  // Direct end labels only when there is room and they do not collide.
  const ends = series
    .map((s) => {
      const last = [...rows].reverse().find((r) => value(r, s.key) !== null)
      return last ? { s, y: y(value(last, s.key)!) } : null
    })
    .filter((e): e is { s: Series; y: number } => e !== null)
    .sort((a, b) => a.y - b.y)
  const endLabels =
    series.length <= 4 && width > 520 && ends.every((e, i) => i === 0 || e.y - ends[i - 1].y >= 14)
  const right = endLabels ? 104 : 16

  const x = linear([0, Math.max(1, n - 1)], [M.left, Math.max(M.left + 10, width - right)])
  const stepX = n > 1 ? x(1) - x(0) : 0
  const xIndex = (key: string) => rows.findIndex((r) => r[xKey] === key)
  const tickEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((width - M.left - right) / 64))))

  const path = (k: string) => {
    let d = ''
    let pen = false
    rows.forEach((r, i) => {
      const v = value(r, k)
      if (v === null) {
        pen = false
        return
      }
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`
      pen = true
    })
    return d
  }

  const moveTo = (clientX: number, el: SVGElement) => {
    const r = el.getBoundingClientRect()
    const i = stepX ? Math.round((clientX - r.left - M.left) / stepX) : 0
    setIdx(Math.max(0, Math.min(n - 1, i)))
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight') setIdx((i) => Math.min(n - 1, (i ?? -1) + 1))
    else if (e.key === 'ArrowLeft') setIdx((i) => Math.max(0, (i ?? n) - 1))
    else return
    e.preventDefault()
  }

  const bandFrom = band ? xIndex(band.from) : -1
  const bandTo = band ? xIndex(band.to) : -1

  return (
    <div ref={ref} className="viz" style={{ height }}>
      {width > 0 && n > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {band && bandFrom >= 0 && bandTo >= 0 && (
            <g>
              <rect
                x={Math.max(M.left, x(bandFrom) - stepX / 2)}
                y={M.top}
                width={Math.min(x(n - 1), x(bandTo) + stepX / 2) - Math.max(M.left, x(bandFrom) - stepX / 2)}
                height={height - M.top - M.bottom}
                className="viz-band"
              />
              <text x={Math.max(M.left, x(bandFrom) - stepX / 2) + 6} y={M.top + 12} className="viz-tick">
                {band.label}
              </text>
            </g>
          )}
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={width - right} y1={y(t)} y2={y(t)} className={t === 0 ? 'viz-baseline' : 'viz-grid'} />
              <text x={M.left - 8} y={y(t) + 4} textAnchor="end" className="viz-tick">
                {fmtTick(t, unit, step)}
              </text>
            </g>
          ))}
          {rows.map((r, i) =>
            i % tickEvery === 0 ? (
              <text key={i} x={x(i)} y={height - 8} textAnchor="middle" className="viz-tick">
                {xLabel(String(r[xKey]))}
              </text>
            ) : null,
          )}
          {markers.map((m) => {
            const i = xIndex(m.x)
            if (i < 0) return null
            return (
              <g key={m.label}>
                <line x1={x(i)} x2={x(i)} y1={M.top} y2={height - M.bottom} className="viz-marker" />
                <text
                  x={i > n * 0.7 ? x(i) - 5 : x(i) + 5}
                  y={M.top + 12}
                  textAnchor={i > n * 0.7 ? 'end' : 'start'}
                  className="viz-tick"
                >
                  {m.label}
                </text>
              </g>
            )
          })}
          {series.map((s) => (
            <path key={s.key} d={path(s.key)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {endLabels &&
            ends.map((e) => (
              <g key={e.s.key}>
                <circle cx={width - right} cy={e.y} r={4} fill={e.s.color} className="viz-dot" />
                <text x={width - right + 10} y={e.y + 4} className="viz-label">
                  {e.s.label}
                </text>
              </g>
            ))}
          {idx !== null && (
            <g pointerEvents="none">
              <line x1={x(idx)} x2={x(idx)} y1={M.top} y2={height - M.bottom} className="viz-crosshair" />
              {series.map((s) => {
                const v = value(rows[idx], s.key)
                return v === null ? null : <circle key={s.key} cx={x(idx)} cy={y(v)} r={4.5} fill={s.color} className="viz-dot" />
              })}
            </g>
          )}
          <rect
            x={M.left - stepX / 2}
            y={M.top}
            width={Math.max(0, width - right - M.left + stepX)}
            height={height - M.top - M.bottom}
            fill="transparent"
            tabIndex={0}
            aria-label={`${ariaLabel}. Use arrow keys to read values.`}
            onPointerMove={(e) => moveTo(e.clientX, e.currentTarget)}
            onPointerLeave={() => setIdx(null)}
            onKeyDown={onKey}
            onFocus={() => setIdx((i) => i ?? n - 1)}
            onBlur={() => setIdx(null)}
            className="viz-overlay"
          />
        </svg>
      )}
      {idx !== null && rows[idx] && (
        <Tooltip x={x(idx)} y={M.top + 8} width={width}>
          <TipTitle>{(tipLabel ?? xLabel)(String(rows[idx][xKey]))}</TipTitle>
          {[...series]
            .sort((a, b) => (value(rows[idx], b.key) ?? -Infinity) - (value(rows[idx], a.key) ?? -Infinity))
            .map((s) => (
              <TipRow key={s.key} color={s.color} label={s.label} value={fmt(value(rows[idx], s.key), unit)} />
            ))}
        </Tooltip>
      )}
    </div>
  )
}
