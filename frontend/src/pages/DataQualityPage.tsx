import { useState } from 'react'
import type { CheckStatus, DataQuality, Definition, DqCheck, ReconciliationRow } from '../api/types'
import { PageData } from '../components/PageData'
import { MatchBadge, StatusBadge } from '../components/ui/Badges'
import { DataTable } from '../components/ui/DataTable'
import { Icon } from '../components/ui/Icon'
import { Card, PageHeader, Segmented } from '../components/ui/Layout'
import { askAnalystHref } from '../lib/router'
import { fmt, titleCase } from '../lib/format'

export function DataQualityPage() {
  return <PageData<DataQuality> path="/api/data-quality">{(d) => <DataQualityView d={d} />}</PageData>
}

type Filter = 'all' | CheckStatus

function DataQualityView({ d }: { d: DataQuality }) {
  const [filter, setFilter] = useState<Filter>('all')
  const checks = filter === 'all' ? d.checks : d.checks.filter((c) => c.status === filter)
  const diffUnit = (r: ReconciliationRow) => (r.unit === 'rate' ? 'rate_diff' : r.unit === 'pct' ? 'pp' : r.unit)

  return (
    <>
      <PageHeader
        eyebrow="Diagnostics"
        title="Data quality"
        description="Checks on the raw data and on the joins between files, and a side-by-side of each dashboard figure with its independent recomputation."
      />

      <div className="status-grid">
        {(['pass', 'warn', 'fail', 'pending'] as CheckStatus[]).map((s) => (
          <button key={s} type="button" className={`status-tile ${filter === s ? 'active' : ''}`} onClick={() => setFilter(filter === s ? 'all' : s)} aria-pressed={filter === s}>
            <StatusBadge value={s} />
            <span className="status-count">{d.summary[s]}</span>
            <span className="muted small">checks</span>
          </button>
        ))}
      </div>

      <Card
        title="Dashboard vs independent figures"
        subtitle="Differences point at a definition or data problem"
        actions={
          d.charts.dq_reconciliation && (
            <a className="btn btn-ghost btn-sm" href={askAnalystHref(`Explain chart:${d.charts.dq_reconciliation.chart_id}`)}>
              <Icon name="sparkle" size={15} /> Explain
            </a>
          )
        }
      >
        <DataTable<ReconciliationRow>
          rowKey={(r) => r.metric_id}
          columns={[
            { key: 'label', header: 'Metric', render: (r) => <strong>{r.label}</strong> },
            { key: 'dash', header: 'Dashboard', align: 'right', render: (r) => fmt(r.dashboard_value, r.unit) },
            { key: 'ind', header: 'Independent', align: 'right', render: (r) => fmt(r.independent_value, r.unit) },
            { key: 'diff', header: 'Difference', align: 'right', render: (r) => fmt(r.difference, diffUnit(r)) },
            { key: 'status', header: 'Status', render: (r) => <MatchBadge value={r.status} /> },
            { key: 'explanation', header: 'Explanation', render: (r) => <span className="muted">{r.explanation ?? ''}</span> },
          ]}
          rows={d.reconciliation}
        />
      </Card>

      <Card
        title="Integrity checks"
        subtitle={`${checks.length} of ${d.checks.length} checks shown`}
        actions={
          <Segmented<Filter>
            label="Filter checks by status"
            value={filter}
            onChange={setFilter}
            options={[{ value: 'all', label: 'All' }, ...(['fail', 'warn', 'pass', 'pending'] as CheckStatus[]).map((s) => ({ value: s, label: titleCase(s) }))]}
          />
        }
      >
        {checks.length ? (
          <DataTable<DqCheck>
            rowKey={(r) => r.check_id}
            columns={[
              { key: 'status', header: 'Status', render: (r) => <StatusBadge value={r.status} /> },
              { key: 'category', header: 'Area', render: (r) => titleCase(r.category) },
              { key: 'label', header: 'Check', render: (r) => <strong>{r.label}</strong> },
              { key: 'expected', header: 'Expected' },
              { key: 'observed', header: 'Observed' },
            ]}
            rows={checks}
          />
        ) : (
          <p className="muted">No checks with this status.</p>
        )}
      </Card>

      <Card title="Metric definitions" subtitle="Definitions the independent figures are built on">
        <DataTable<Definition>
          rowKey={(r) => r.metric_id}
          columns={[
            { key: 'name', header: 'Metric', render: (r) => <strong>{r.name}</strong> },
            { key: 'definition', header: 'Definition' },
            { key: 'grain', header: 'Grain' },
          ]}
          rows={d.definitions}
        />
      </Card>
    </>
  )
}
