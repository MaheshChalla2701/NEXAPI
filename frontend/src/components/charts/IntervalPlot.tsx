import { useState } from 'react'
import { fmt, fmtTick, type FormatUnit } from '../../lib/format'
import { useWidth } from '../../lib/hooks'
import { linear, niceTicks, truncate } from '../../lib/scale'
import { TipRow, TipTitle, Tooltip } from './ChartFrame'

export interface IntervalRow {
  label: string
  effect: number
  low: number
  high: number
  detail?: string
}

const ROW = 44
const AXIS = 28

export function intervalColor(r: { low: number; high: number; effect: number }) {
  if (r.low <= 0 && r.high >= 0) return 'var(--viz-neutral)'
  return r.effect > 0 ? 'var(--viz-pos)' : 'var(--viz-neg)'
}

/** Point estimate with 95% interval per row, against a zero reference line. */
export function IntervalPlot({ rows, unit, ariaLabel }: { rows: IntervalRow[]; unit: FormatUnit; ariaLabel: string }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null)
  const ext = rows.flatMap((r) => [r.low, r.high, 0])
  const { ticks, step } = niceTicks(Math.min(...ext), Math.max(...ext), width < 480 ? 4 : 6)
  const labelW = Math.min(210, Math.max(110, width * 0.3))
  const valueW = width < 520 ? 70 : 170
  const left = labelW + 12
  const right = Math.max(left + 60, width - valueW - 8)
  const x = linear([ticks[0], ticks[ticks.length - 1]], [left, right])
  const height = rows.length * ROW + AXIS

  return (
    <div ref={ref} className="viz" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="group" aria-label={ariaLabel}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={0} y2={height - AXIS} className={t === 0 ? 'viz-baseline strong' : 'viz-grid'} />
              <text x={x(t)} y={height - AXIS + 18} textAnchor="middle" className="viz-tick">
                {fmtTick(t, unit, step)}
              </text>
            </g>
          ))}
          {rows.map((r, i) => {
            const cy = i * ROW + ROW / 2
            const c = intervalColor(r)
            const active = hover?.i === i
            return (
              <g
                key={r.label}
                tabIndex={0}
                role="img"
                aria-label={`${r.label}: ${fmt(r.effect, unit)}, 95% interval ${fmt(r.low, unit)} to ${fmt(r.high, unit)}`}
                className={`viz-row ${hover && !active ? 'dim' : ''}`}
                onPointerMove={(e) => {
                  const b = e.currentTarget.ownerSVGElement!.getBoundingClientRect()
                  setHover({ i, x: e.clientX - b.left, y: e.clientY - b.top })
                }}
                onPointerLeave={() => setHover(null)}
                onFocus={() => setHover({ i, x: x(r.high), y: cy })}
                onBlur={() => setHover(null)}
              >
                <rect x={0} y={i * ROW} width={width} height={ROW} fill="transparent" />
                <text x={0} y={cy + 4} className="viz-label">
                  {truncate(r.label, Math.floor(labelW / 6.6))}
                  <title>{r.label}</title>
                </text>
                <line x1={x(r.low)} x2={x(r.high)} y1={cy} y2={cy} stroke={c} strokeWidth={2} strokeLinecap="round" />
                <line x1={x(r.low)} x2={x(r.low)} y1={cy - 5} y2={cy + 5} stroke={c} strokeWidth={2} />
                <line x1={x(r.high)} x2={x(r.high)} y1={cy - 5} y2={cy + 5} stroke={c} strokeWidth={2} />
                <circle cx={x(r.effect)} cy={cy} r={5} fill={c} className="viz-dot" />
                <text x={width - 4} y={cy + 4} textAnchor="end" className="viz-value">
                  {width < 520 ? fmt(r.effect, unit) : `${fmt(r.effect, unit)}  (${fmt(r.low, unit)} to ${fmt(r.high, unit)})`}
                </text>
              </g>
            )
          })}
        </svg>
      )}
      {hover && rows[hover.i] && (
        <Tooltip x={hover.x} y={hover.y} width={width}>
          <TipTitle>{rows[hover.i].label}</TipTitle>
          <TipRow color={intervalColor(rows[hover.i])} label="effect (treatment − control)" value={fmt(rows[hover.i].effect, unit)} />
          <TipRow label="95% interval" value={`${fmt(rows[hover.i].low, unit)} to ${fmt(rows[hover.i].high, unit)}`} />
          {rows[hover.i].detail && <p className="tip-note">{rows[hover.i].detail}</p>}
        </Tooltip>
      )}
    </div>
  )
}
