import type { FunnelStage, Meta, Referrals, Row } from '../api/types'
import { ChartFrame } from '../components/charts/ChartFrame'
import { FunnelChart } from '../components/charts/FunnelChart'
import { LineChart } from '../components/charts/LineChart'
import { InitiativeHeader } from '../components/InitiativeHeader'
import { PageData } from '../components/PageData'
import { KpiTile, Note, PageHeader } from '../components/ui/Layout'
import { dayLabel, fmt } from '../lib/format'

export function ReferralsPage() {
  return <PageData<Referrals> path="/api/referrals">{(d, meta) => <ReferralsView d={d} meta={meta} />}</PageData>
}

function ReferralsView({ d, meta }: { d: Referrals; meta: Meta }) {
  const m = Object.fromEntries(d.metrics.map((x) => [x.metric_id, x]))
  const firstReferred = d.weekly_signups.find((r) => Number(r.referred ?? 0) > 0)
  const weeks = d.weekly_signups.map((r) => String(r.week_start))
  const series = [
    { key: 'organic', label: 'Organic', color: 'var(--s1)' },
    { key: 'referred', label: 'Referred', color: 'var(--s2)' },
  ]
  const tile = (id: string, label?: string) => {
    const x = m[id]
    return x ? <KpiTile key={id} label={label ?? x.label} value={fmt(x.value, x.unit)} sub={x.note?.replace(/^MOCK\.?\s*/, '') || undefined} /> : null
  }

  return (
    <>
      <PageHeader
        eyebrow="Initiative 3"
        title="Partner referral programme"
        description="Follows referred workspaces from the referral log to paying customers, and sets partner payouts (a cost) against the revenue they bring in."
      />
      <InitiativeHeader initiative={d.initiative} isMock={meta.is_mock} />

      <ChartFrame
        title="Referral funnel"
        subtitle="Workspaces remaining at each step, from referral record to still paying after 30 days"
        info={d.charts.referral_funnel}
        table={{
          columns: [
            { key: 'stage', header: 'Stage' },
            { key: 'count', header: 'Workspaces', align: 'right', render: (r: FunnelStage) => fmt(r.count, 'count') },
            { key: 'note', header: 'Note', render: (r: FunnelStage) => r.note ?? '' },
          ],
          rows: d.funnel,
        }}
      >
        <FunnelChart steps={d.funnel.map((s) => ({ label: s.stage, value: s.count, note: s.note }))} />
      </ChartFrame>

      <h2 className="section-title">Acquisition economics</h2>
      <div className="kpi-grid">
        {tile('payouts_owed')}
        {tile('payouts_paid')}
        {tile('cost_per_paid')}
        {tile('referred_revenue')}
        {m.incremental_customers && (
          <KpiTile
            label={m.incremental_customers.label}
            value={m.incremental_customers.value === null ? 'Not established' : fmt(m.incremental_customers.value, 'count')}
            sub={m.incremental_customers.note ?? undefined}
          />
        )}
      </div>

      <ChartFrame
        title="Weekly sign-ups by source"
        subtitle={weeks.length ? `Sign-ups per week, ${dayLabel(weeks[0], true)} – ${dayLabel(weeks[weeks.length - 1], true)}` : undefined}
        info={d.charts.referral_weekly_signups}
        legend={series.map((s) => ({ label: s.label, color: s.color, shape: 'line' as const }))}
        table={{
          columns: [
            { key: 'week_start', header: 'Week starting', render: (r: Row) => dayLabel(String(r.week_start), true) },
            ...series.map((s) => ({ key: s.key, header: s.label, align: 'right' as const, render: (r: Row) => fmt(r[s.key] as number, 'count') })),
          ],
          rows: d.weekly_signups,
        }}
      >
        <LineChart
          rows={d.weekly_signups}
          xKey="week_start"
          series={series}
          unit="count"
          zeroBased
          xLabel={(w) => dayLabel(w)}
          tipLabel={(w) => `Week of ${dayLabel(w, true)}`}
          markers={firstReferred ? [{ x: String(firstReferred.week_start), label: 'Referrals begin' }] : []}
          ariaLabel="Weekly sign-ups, organic and referred"
        />
      </ChartFrame>

      <Note tone="warning">
        A referred customer is not automatically an extra customer: some would have signed up anyway. Partner payouts
        are a programme cost and are reported separately from revenue, never subtracted from it.
      </Note>
    </>
  )
}
