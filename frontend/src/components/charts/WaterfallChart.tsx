import { useState } from 'react'
import { fmt, fmtTick } from '../../lib/format'
import { useSvgId, useWidth } from '../../lib/hooks'
import { linear, niceTicks, truncate } from '../../lib/scale'
import { HatchPattern, TipRow, TipTitle, Tooltip } from './ChartFrame'

export interface WaterfallItem {
  label: string
  value: number
  low?: number
  high?: number
  kind: 'driver' | 'unexplained' | 'total'
  confidence?: string
  detail?: string
}

const ROW = 44
const BAR = 20
const AXIS = 30

/** Horizontal waterfall in percentage points: each cause starts where the last ended. */
export function WaterfallChart({ items }: { items: WaterfallItem[] }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null)
  const hatchId = useSvgId('hatch')

  let cum = 0
  const geo = items.map((it) => {
    if (it.kind === 'total') return { from: 0, to: it.value, lo: undefined, hi: undefined }
    const from = cum
    cum += it.value
    return {
      from,
      to: cum,
      lo: it.low !== undefined ? from + it.low : undefined,
      hi: it.high !== undefined ? from + it.high : undefined,
    }
  })
  const extent = geo.flatMap((g) => [g.from, g.to, g.lo ?? g.from, g.hi ?? g.to, 0])
  const { ticks, step } = niceTicks(Math.min(...extent), Math.max(...extent), width < 480 ? 4 : 6)

  const labelW = Math.min(230, Math.max(110, width * 0.32))
  const valueW = 72
  const left = labelW + 12
  const right = Math.max(left + 60, width - valueW - 8)
  const x = linear([ticks[0], ticks[ticks.length - 1]], [left, right])
  const height = items.length * ROW + AXIS
  const rowY = (i: number) => i * ROW

  const color = (it: WaterfallItem) =>
    it.kind === 'total'
      ? 'var(--viz-total)'
      : it.kind === 'unexplained'
        ? 'var(--viz-neutral)'
        : it.value >= 0
          ? 'var(--viz-pos)'
          : 'var(--viz-neg)'

  return (
    <div ref={ref} className="viz" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="group" aria-label="Revenue bridge waterfall chart">
          <defs>
            <HatchPattern id={hatchId} color="var(--viz-neutral)" />
          </defs>
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={x(t)}
                x2={x(t)}
                y1={0}
                y2={height - AXIS}
                className={t === 0 ? 'viz-baseline' : 'viz-grid'}
              />
              <text x={x(t)} y={height - AXIS + 18} className="viz-tick" textAnchor="middle">
                {fmtTick(t, 'pp', step)}
              </text>
            </g>
          ))}

          {geo.map((g, i) => {
            const next = geo[i + 1]
            if (!next || items[i].kind === 'total') return null
            return (
              <line
                key={`c${i}`}
                className="viz-connector"
                x1={x(g.to)}
                x2={x(g.to)}
                y1={rowY(i) + (ROW + BAR) / 2}
                y2={rowY(i + 1) + (ROW - BAR) / 2}
              />
            )
          })}

          {items.map((it, i) => {
            const g = geo[i]
            const y = rowY(i) + (ROW - BAR) / 2
            const x0 = Math.min(x(g.from), x(g.to))
            const w = Math.max(2, Math.abs(x(g.to) - x(g.from)))
            const active = hover?.i === i
            const show = (px: number, py: number) => setHover({ i, x: px, y: py })
            return (
              <g
                key={it.label}
                tabIndex={0}
                role="img"
                aria-label={`${it.label}: ${fmt(it.value, 'pp')}`}
                className={`viz-row ${hover && !active ? 'dim' : ''}`}
                onPointerMove={(e) => {
                  const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect()
                  show(e.clientX - r.left, e.clientY - r.top)
                }}
                onPointerLeave={() => setHover(null)}
                onFocus={() => show(x(g.to), y)}
                onBlur={() => setHover(null)}
              >
                <rect x={0} y={rowY(i)} width={width} height={ROW} fill="transparent" />
                {i > 0 && items[i].kind === 'total' && (
                  <line x1={0} x2={width} y1={rowY(i)} y2={rowY(i)} className="viz-grid" />
                )}
                <text
                  x={0}
                  y={rowY(i) + ROW / 2 + 4}
                  className={`viz-label ${it.kind === 'total' ? 'strong' : ''}`}
                >
                  {truncate(it.label, Math.floor(labelW / 6.6))}
                  <title>{it.label}</title>
                </text>
                <rect x={x0} y={y} width={w} height={BAR} rx={3} fill={color(it)} />
                {it.kind === 'unexplained' && (
                  <rect x={x0} y={y} width={w} height={BAR} rx={3} fill={`url(#${hatchId})`} />
                )}
                {g.lo !== undefined && g.hi !== undefined && (
                  <g className="viz-whisker">
                    <line x1={x(g.lo)} x2={x(g.hi)} y1={y + BAR / 2} y2={y + BAR / 2} />
                    <line x1={x(g.lo)} x2={x(g.lo)} y1={y + 4} y2={y + BAR - 4} />
                    <line x1={x(g.hi)} x2={x(g.hi)} y1={y + 4} y2={y + BAR - 4} />
                  </g>
                )}
                <text
                  x={width - 4}
                  y={rowY(i) + ROW / 2 + 4}
                  textAnchor="end"
                  className={`viz-value ${it.kind === 'total' ? 'strong' : ''}`}
                >
                  {fmt(it.value, 'pp')}
                </text>
              </g>
            )
          })}
        </svg>
      )}
      {hover && (
        <Tooltip x={hover.x} y={hover.y} width={width}>
          <TipTitle>{items[hover.i].label}</TipTitle>
          <TipRow color={color(items[hover.i])} label="central estimate" value={fmt(items[hover.i].value, 'pp')} />
          {items[hover.i].low !== undefined && (
            <TipRow
              label="range"
              value={`${fmt(items[hover.i].low, 'pp')} to ${fmt(items[hover.i].high, 'pp')}`}
            />
          )}
          {items[hover.i].confidence && <TipRow label="confidence" value={items[hover.i].confidence!} />}
          {items[hover.i].detail && <p className="tip-note">{items[hover.i].detail}</p>}
        </Tooltip>
      )}
    </div>
  )
}
