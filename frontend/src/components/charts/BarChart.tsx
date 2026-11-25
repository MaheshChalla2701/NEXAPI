import { useState } from 'react'
import { fmt, fmtTick, type FormatUnit } from '../../lib/format'
import { useWidth } from '../../lib/hooks'
import { barPath, linear, niceTicks } from '../../lib/scale'
import type { Series } from './LineChart'
import { TipRow, TipTitle, Tooltip } from './ChartFrame'

interface Props {
  categories: { key: string; label: string }[]
  series: Series[]
  values: Record<string, Record<string, number | null>>
  unit: FormatUnit
  height?: number
  ariaLabel: string
}

const M = { top: 22, bottom: 34, left: 56, right: 12 }
const GAP = 2

/** Grouped column chart: bars capped at 24px, rounded at the data end, 2px gaps. */
export function BarChart({ categories, series, values, unit, height = 240, ariaLabel }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<{ c: string; s: string; x: number; y: number } | null>(null)

  const all = categories.flatMap((c) => series.map((s) => values[c.key]?.[s.key] ?? null)).filter((v): v is number => v !== null)
  const { ticks, step } = niceTicks(Math.min(0, ...all), Math.max(0, ...all), 4)
  const y = linear([ticks[0], ticks[ticks.length - 1]], [height - M.bottom, M.top])
  const band = (width - M.left - M.right) / Math.max(1, categories.length)
  const barW = Math.max(4, Math.min(24, (band * 0.7 - GAP * (series.length - 1)) / series.length))
  const groupW = series.length * barW + (series.length - 1) * GAP
  // Direct value labels only where they cannot collide (single series); otherwise tooltip + table view.
  const labelBars = series.length === 1 && band >= 56

  return (
    <div ref={ref} className="viz" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={width - M.right} y1={y(t)} y2={y(t)} className={t === 0 ? 'viz-baseline' : 'viz-grid'} />
              <text x={M.left - 8} y={y(t) + 4} textAnchor="end" className="viz-tick">
                {fmtTick(t, unit, step)}
              </text>
            </g>
          ))}
          {categories.map((c, ci) => {
            const gx = M.left + ci * band + (band - groupW) / 2
            return (
              <g key={c.key}>
                <text x={M.left + ci * band + band / 2} y={height - 12} textAnchor="middle" className="viz-tick">
                  {c.label}
                </text>
                {series.map((s, si) => {
                  const v = values[c.key]?.[s.key]
                  if (v === null || v === undefined) return null
                  const bx = gx + si * (barW + GAP)
                  const active = hover?.c === c.key && hover?.s === s.key
                  return (
                    <g
                      key={s.key}
                      tabIndex={0}
                      role="img"
                      aria-label={`${c.label}, ${s.label}: ${fmt(v, unit)}`}
                      onPointerMove={(e) => {
                        const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect()
                        setHover({ c: c.key, s: s.key, x: e.clientX - r.left, y: e.clientY - r.top })
                      }}
                      onPointerLeave={() => setHover(null)}
                      onFocus={() => setHover({ c: c.key, s: s.key, x: bx + barW, y: y(v) })}
                      onBlur={() => setHover(null)}
                      className={`viz-bar ${hover && !active ? 'dim' : ''}`}
                    >
                      <rect x={bx - GAP} y={M.top} width={barW + 2 * GAP} height={height - M.top - M.bottom} fill="transparent" />
                      <path d={barPath(bx, y(0), y(v), barW)} fill={s.color} />
                      {labelBars && (
                        <text x={bx + barW / 2} y={v >= 0 ? y(v) - 6 : y(v) + 14} textAnchor="middle" className="viz-value small">
                          {fmt(v, unit, { compact: true })}
                        </text>
                      )}
                    </g>
                  )
                })}
              </g>
            )
          })}
        </svg>
      )}
      {hover && (
        <Tooltip x={hover.x} y={hover.y} width={width}>
          <TipTitle>{categories.find((c) => c.key === hover.c)?.label}</TipTitle>
          {series.map((s) => (
            <TipRow key={s.key} color={s.color} label={s.label} value={fmt(values[hover.c]?.[s.key], unit)} />
          ))}
        </Tooltip>
      )}
    </div>
  )
}
