import { useState } from 'react'
import type { Cohort, Definition, Meta, Retention, Row } from '../api/types'
import { ChartFrame } from '../components/charts/ChartFrame'
import { CohortHeatmap } from '../components/charts/CohortHeatmap'
import { LineChart } from '../components/charts/LineChart'
import { PageData } from '../components/PageData'
import { DataTable } from '../components/ui/DataTable'
import { Card, KpiTile, PageHeader, Segmented } from '../components/ui/Layout'
import { dayLabel, fmt, monthLabel, titleCase } from '../lib/format'

export function RetentionPage() {
  const [segment, setSegment] = useState('all')
  return (
    <PageData<Retention> path={`/api/retention?segment=${encodeURIComponent(segment)}`}>
      {(d, meta) => <RetentionView d={d} meta={meta} setSegment={setSegment} />}
    </PageData>
  )
}

function RetentionView({ d, meta, setSegment }: { d: Retention; meta: Meta; setSegment: (s: string) => void }) {
  const k = (id: string) => d.kpis[id]?.value ?? null
  const weeks = d.acquisition.map((r) => String(r.week_start))
  const range = weeks.length ? `${dayLabel(weeks[0], true)} – ${dayLabel(weeks[weeks.length - 1], true)}` : ''
  const signupSeries = [
    { key: 'organic_signups', label: 'Organic', color: 'var(--s1)' },
    { key: 'referred_signups', label: 'Referred', color: 'var(--s2)' },
  ]
  const convSeries = [
    { key: 'organic_conversion', label: 'Organic', color: 'var(--s1)' },
    { key: 'referred_conversion', label: 'Referred', color: 'var(--s2)' },
  ]
  // Weeks with no referred sign-ups have no referred conversion rate (null), so the line starts at launch.
  const legend = signupSeries.map((s) => ({ label: s.label, color: s.color, shape: 'line' as const }))
  const weekTable = (series: typeof signupSeries, unit: 'count' | 'rate') => ({
    columns: [
      { key: 'week_start', header: 'Week starting', render: (r: Row) => dayLabel(String(r.week_start), true) },
      ...series.map((s) => ({ key: s.key, header: s.label, align: 'right' as const, render: (r: Row) => fmt(r[s.key] as number, unit) })),
    ],
    rows: d.acquisition,
  })
  const cohortRows = d.cohorts.flatMap((c: Cohort) => d.days.map((day) => ({ cohort: c.cohort_month, day, size: c.cohort_size, rate: c.rates[String(day)] })))
  const retentionNote = d.kpis.retention30_q3_independent?.note?.replace(/^MOCK value\.\s*/, '')

  return (
    <>
      <PageHeader
        eyebrow="Diagnostics"
        title="Retention & acquisition"
        description="Re-derives the dashboard's 30-day retention and sign-up figures from cohorts, so the definitions, denominators and cohort maturity are visible."
      />

      <div className="kpi-grid">
        <KpiTile label="30-day retention, Q2" value={fmt(k('retention30_q2_independent'), 'rate')} sub={`Dashboard: ${fmt(k('retention30_q2_reported'), 'rate')}`} />
        <KpiTile
          label="30-day retention, Q3"
          value={fmt(k('retention30_q3_independent'), 'rate')}
          sub={
            <>
              Dashboard: {fmt(k('retention30_q3_reported'), 'rate')}
              {retentionNote && <span className="kpi-warn"> · {retentionNote}</span>}
            </>
          }
        />
        <KpiTile label="Sign-ups, Q2 → Q3" value={`${fmt(k('signups_q2'), 'count')} → ${fmt(k('signups_q3'), 'count')}`} sub={`Growth ${fmt(k('signup_growth_pct'), 'pct')} · dashboard ${fmt(k('signup_growth_pct_reported'), 'pct')}`} />
      </div>

      <ChartFrame
        title="Cohort retention"
        subtitle={`Share of each monthly sign-up cohort still active N days after sign-up · segment: ${titleCase(d.segment)} · as of ${dayLabel(meta.as_of_date, true)}`}
        info={d.charts.retention_cohorts}
        table={{
          columns: [
            { key: 'cohort', header: 'Cohort', render: (r: (typeof cohortRows)[number]) => monthLabel(r.cohort, true) },
            { key: 'day', header: 'Day', align: 'right' },
            { key: 'size', header: 'Cohort size', align: 'right', render: (r: (typeof cohortRows)[number]) => fmt(r.size, 'count') },
            { key: 'rate', header: 'Still active', align: 'right', render: (r: (typeof cohortRows)[number]) => (r.rate === null ? 'Not mature' : fmt(r.rate, 'rate')) },
          ],
          rows: cohortRows,
        }}
      >
        <div className="filter-row">
          <Segmented label="Segment" value={d.segment} onChange={setSegment} options={d.segments.map((s) => ({ value: s, label: titleCase(s) }))} />
        </div>
        {d.cohorts.length ? <CohortHeatmap cohorts={d.cohorts} days={d.days} /> : <p className="muted">No cohorts for this segment.</p>}
      </ChartFrame>

      <div className="grid-2">
        <ChartFrame title="Weekly sign-ups by source" subtitle={`Sign-ups per week, ${range}`} info={d.charts.acquisition_signups} legend={legend} table={weekTable(signupSeries, 'count')}>
          <LineChart rows={d.acquisition} xKey="week_start" series={signupSeries} unit="count" zeroBased xLabel={(w) => dayLabel(w)} tipLabel={(w) => `Week of ${dayLabel(w, true)}`} ariaLabel="Weekly sign-ups by source" />
        </ChartFrame>
        <ChartFrame title="Weekly paid conversion by source" subtitle={`Paid conversions ÷ sign-ups, ${range}`} info={d.charts.acquisition_conversion} legend={legend} table={weekTable(convSeries, 'rate')}>
          <LineChart rows={d.acquisition} xKey="week_start" series={convSeries} unit="rate" zeroBased xLabel={(w) => dayLabel(w)} tipLabel={(w) => `Week of ${dayLabel(w, true)}`} ariaLabel="Weekly paid conversion by source" />
        </ChartFrame>
      </div>

      <Card title="Metric definitions" subtitle="How each figure on this page is defined">
        <DataTable<Definition>
          rowKey={(r) => r.metric_id}
          columns={[
            { key: 'name', header: 'Metric', render: (r) => <strong>{r.name}</strong> },
            { key: 'definition', header: 'Definition' },
            { key: 'grain', header: 'Grain' },
            { key: 'caveats', header: 'Status', render: (r) => <span className="muted">{r.caveats ?? ''}</span> },
          ]}
          rows={d.definitions}
        />
      </Card>
    </>
  )
}
