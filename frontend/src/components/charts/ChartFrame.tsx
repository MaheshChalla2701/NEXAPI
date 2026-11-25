import { useState, type ReactNode } from 'react'
import type { ChartInfo } from '../../api/types'
import { askAnalystHref } from '../../lib/router'
import { DataTable, type Column } from '../ui/DataTable'
import { Icon } from '../ui/Icon'

export interface LegendItem {
  label: string
  color: string
  shape?: 'rect' | 'line' | 'hatch' | 'whisker'
}

export interface TableView<R extends object> {
  columns: Column<R>[]
  rows: R[]
}

/**
 * Every chart sits in a frame with: a title stating the measure and unit, a
 * subtitle with the period, a legend (for 2+ series), a table view toggle so no
 * value is only reachable by hovering, and a link to have the analyst explain it.
 */
export function ChartFrame<R extends object>({
  title,
  subtitle,
  info,
  legend,
  table,
  children,
  footnote,
}: {
  title: string
  subtitle?: ReactNode
  info?: ChartInfo
  legend?: LegendItem[]
  table: TableView<R>
  children: ReactNode
  footnote?: ReactNode
}) {
  const [showTable, setShowTable] = useState(false)
  return (
    <figure className="card chart-card">
      <div className="card-head">
        <div>
          <h2 className="card-title">{title}</h2>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
        <div className="card-actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-pressed={showTable}
            onClick={() => setShowTable((v) => !v)}
          >
            <Icon name={showTable ? 'bridge' : 'table'} size={15} />
            {showTable ? 'Chart' : 'Table'}
          </button>
          {info && (
            <a className="btn btn-ghost btn-sm" href={askAnalystHref(`Explain chart:${info.chart_id}`)}>
              <Icon name="sparkle" size={15} /> Explain
            </a>
          )}
        </div>
      </div>
      {legend && legend.length > 0 && !showTable && <Legend items={legend} />}
      <div className="chart-body">
        {showTable ? <DataTable columns={table.columns} rows={table.rows} caption={title} /> : children}
      </div>
      {footnote && <figcaption className="chart-foot">{footnote}</figcaption>}
    </figure>
  )
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((it) => (
        <li key={it.label}>
          <span className={`legend-key legend-${it.shape ?? 'rect'}`} style={{ ['--key' as string]: it.color }} />
          {it.label}
        </li>
      ))}
    </ul>
  )
}

export function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  const flip = x > width - 220
  return (
    <div
      className="viz-tooltip"
      role="status"
      style={{ left: flip ? undefined : x + 14, right: flip ? width - x + 14 : undefined, top: Math.max(4, y - 12) }}
    >
      {children}
    </div>
  )
}

export function TipTitle({ children }: { children: ReactNode }) {
  return <div className="tip-title">{children}</div>
}

export function TipRow({ color, label, value }: { color?: string; label: string; value: string }) {
  return (
    <div className="tip-row">
      {color ? <span className="tip-key" style={{ background: color }} /> : <span className="tip-key-empty" />}
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

export function HatchPattern({ id, color }: { id: string; color: string }) {
  return (
    <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill={color} opacity="0.35" />
      <line x1="0" y1="0" x2="0" y2="6" stroke={color} strokeWidth="2.5" />
    </pattern>
  )
}
