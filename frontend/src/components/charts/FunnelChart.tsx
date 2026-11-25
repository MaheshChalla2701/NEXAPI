import { useState } from 'react'
import { fmt } from '../../lib/format'
import { useWidth } from '../../lib/hooks'
import { truncate } from '../../lib/scale'
import { TipRow, TipTitle, Tooltip } from './ChartFrame'

export interface FunnelStep {
  label: string
  value: number
  note?: string | null
}

const ROW = 52
const BAR = 22

/** Horizontal funnel: bar length = share of the first stage; step conversion under each label. */
export function FunnelChart({ steps }: { steps: FunnelStep[] }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null)
  const first = steps[0]?.value || 1
  const labelW = Math.min(230, Math.max(130, width * 0.32))
  const valueW = 110
  const left = labelW + 12
  const plotW = Math.max(40, width - left - valueW - 8)
  const height = steps.length * ROW

  return (
    <div ref={ref} className="viz" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="group" aria-label="Referral funnel">
          {steps.map((s, i) => {
            const y0 = i * ROW
            const w = Math.max(2, (s.value / first) * plotW)
            const prev = i > 0 ? steps[i - 1].value : null
            const active = hover?.i === i
            return (
              <g
                key={s.label}
                tabIndex={0}
                role="img"
                aria-label={`${s.label}: ${fmt(s.value, 'count')}`}
                className={`viz-row ${hover && !active ? 'dim' : ''}`}
                onPointerMove={(e) => {
                  const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect()
                  setHover({ i, x: e.clientX - r.left, y: e.clientY - r.top })
                }}
                onPointerLeave={() => setHover(null)}
                onFocus={() => setHover({ i, x: left + w, y: y0 + 10 })}
                onBlur={() => setHover(null)}
              >
                <rect x={0} y={y0} width={width} height={ROW} fill="transparent" />
                <text x={0} y={y0 + 22} className="viz-label">
                  {truncate(s.label, Math.floor(labelW / 6.6))}
                  <title>{s.label}</title>
                </text>
                {prev !== null && (
                  <text x={0} y={y0 + 39} className="viz-tick">
                    {prev ? `${((s.value / prev) * 100).toFixed(1)}% of previous step` : '—'}
                  </text>
                )}
                <rect x={left} y={y0 + (ROW - BAR) / 2} width={plotW} height={BAR} rx={4} className="viz-track" />
                <rect x={left} y={y0 + (ROW - BAR) / 2} width={w} height={BAR} rx={4} fill="var(--s1)" />
                <text x={width - 4} y={y0 + 22} textAnchor="end" className="viz-value strong">
                  {fmt(s.value, 'count')}
                </text>
                <text x={width - 4} y={y0 + 39} textAnchor="end" className="viz-tick">
                  {((s.value / first) * 100).toFixed(1)}% of start
                </text>
              </g>
            )
          })}
        </svg>
      )}
      {hover && steps[hover.i] && (
        <Tooltip x={hover.x} y={hover.y} width={width}>
          <TipTitle>{steps[hover.i].label}</TipTitle>
          <TipRow color="var(--s1)" label="workspaces" value={fmt(steps[hover.i].value, 'count')} />
          <TipRow label="of first stage" value={`${((steps[hover.i].value / first) * 100).toFixed(1)}%`} />
          {steps[hover.i].note && <p className="tip-note">{steps[hover.i].note}</p>}
        </Tooltip>
      )}
    </div>
  )
}
