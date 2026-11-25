import { useState } from 'react'
import type { Cohort } from '../../api/types'
import { fmt, monthLabel } from '../../lib/format'
import { useWidth } from '../../lib/hooks'
import { TipRow, TipTitle, Tooltip } from './ChartFrame'

const STEPS = 7 // --ramp-0 … --ramp-6 (sequential blue, light → dark)

/** Cohort retention grid. Sequential one-hue ramp; immature cells are hatched, never coloured. */
export function CohortHeatmap({ cohorts, days }: { cohorts: Cohort[]; days: number[] }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<{ c: number; d: number; x: number; y: number } | null>(null)
  const values = cohorts.flatMap((c) => days.map((d) => c.rates[String(d)])).filter((v): v is number => v !== null)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const step = (v: number) => (hi === lo ? 3 : Math.min(STEPS - 1, Math.floor(((v - lo) / (hi - lo)) * STEPS)))

  return (
    <div ref={ref} className="heatmap-wrap">
      <table className="heatmap">
        <thead>
          <tr>
            <th scope="col">Sign-up cohort</th>
            <th scope="col" className="num">Size</th>
            {days.map((d) => (
              <th key={d} scope="col" className="num">
                Day {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cohorts.map((c, ci) => (
            <tr key={c.cohort_month}>
              <th scope="row">{monthLabel(c.cohort_month, true)}</th>
              <td className="num muted">{fmt(c.cohort_size, 'count')}</td>
              {days.map((d, di) => {
                const v = c.rates[String(d)]
                const show = (x: number, y: number) => setHover({ c: ci, d: di, x, y })
                return (
                  <td
                    key={d}
                    tabIndex={0}
                    className={v === null ? 'cell immature' : `cell heat-${step(v)}`}
                    aria-label={`${monthLabel(c.cohort_month, true)} cohort, day ${d}: ${v === null ? 'not yet mature' : fmt(v, 'rate')}`}
                    onPointerMove={(e) => {
                      const r = (ref.current as HTMLElement).getBoundingClientRect()
                      show(e.clientX - r.left, e.clientY - r.top)
                    }}
                    onPointerLeave={() => setHover(null)}
                    onFocus={(e) => {
                      const r = (ref.current as HTMLElement).getBoundingClientRect()
                      const t = e.currentTarget.getBoundingClientRect()
                      show(t.right - r.left, t.top - r.top)
                    }}
                    onBlur={() => setHover(null)}
                  >
                    {v === null ? '' : fmt(v, 'rate', { digits: 0 })}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="heat-legend" aria-hidden="true">
        <span>{fmt(lo, 'rate', { digits: 0 })}</span>
        <span className="heat-scale">
          {Array.from({ length: STEPS }, (_, i) => (
            <span key={i} className={`heat-${i}`} />
          ))}
        </span>
        <span>{fmt(hi, 'rate', { digits: 0 })}</span>
        <span className="heat-immature-key" /> <span>Cohort too young to measure</span>
      </div>
      {hover && (
        <Tooltip x={hover.x} y={hover.y} width={width}>
          <TipTitle>
            {monthLabel(cohorts[hover.c].cohort_month, true)} cohort · day {days[hover.d]}
          </TipTitle>
          <TipRow
            label="still active"
            value={
              cohorts[hover.c].rates[String(days[hover.d])] === null
                ? 'Not yet mature'
                : fmt(cohorts[hover.c].rates[String(days[hover.d])], 'rate')
            }
          />
          <TipRow label="workspaces in cohort" value={fmt(cohorts[hover.c].cohort_size, 'count')} />
        </Tooltip>
      )}
    </div>
  )
}
