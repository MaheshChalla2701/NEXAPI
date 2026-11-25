import type { ReactNode } from 'react'

export interface Column<R> {
  key: string
  header: string
  align?: 'left' | 'right' | 'center'
  render?: (row: R) => ReactNode
  width?: string
}

export function DataTable<R extends object>({
  columns,
  rows,
  caption,
  rowKey,
}: {
  columns: Column<R>[]
  rows: R[]
  caption?: string
  rowKey?: (row: R, i: number) => string
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ textAlign: c.align ?? 'left', width: c.width }} scope="col">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r, i) : i}>
              {columns.map((c) => (
                <td key={c.key} style={{ textAlign: c.align ?? 'left' }} className={c.align === 'right' ? 'num' : ''}>
                  {c.render ? c.render(r) : String((r as Record<string, unknown>)[c.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
