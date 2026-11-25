import type { BridgeItem, Meta, Overview } from '../api/types'
import { ChartFrame } from '../components/charts/ChartFrame'
import { LineChart } from '../components/charts/LineChart'
import { PageData } from '../components/PageData'
import { RecommendationBadge } from '../components/ui/Badges'
import { Icon } from '../components/ui/Icon'
import { Card, KpiTile, PageHeader } from '../components/ui/Layout'
import { fmt, monthLabel, periodLabel } from '../lib/format'
import { href } from '../lib/router'

const SERIES_COLORS = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)']

export function OverviewPage() {
  return <PageData<Overview> path="/api/overview">{(d, meta) => <OverviewView d={d} meta={meta} />}</PageData>
}

function OverviewView({ d, meta }: { d: Overview; meta: Meta }) {
  const v = (id: string) => d.kpis[id]?.value ?? null
  const months = d.revenue_trend.rows.map((r) => String(r.month))
  const q3 = months.filter((m) => m.endsWith('-07') || m.endsWith('-08') || m.endsWith('-09'))
  const series = d.revenue_trend.regions.map((r, i) => ({ key: r, label: r, color: SERIES_COLORS[i % 4] }))

  return (
    <>
      <PageHeader
        eyebrow="THE BIG PICTURE / Q2 TO Q3"
        title="Growth, in perspective."
        actions={<a className="btn btn-primary" href={href('analyst')}><Icon name="sparkle" size={17} /> Ask your analyst</a>}
        description={
          <>
            How revenue moved between Q2 ({periodLabel(meta.q2_period)}) and Q3 ({periodLabel(meta.q3_period)}), what
            drove it, and where each Q3 initiative stands.
          </>
        }
      />

      <div className="kpi-grid overview-kpis">
        <KpiTile
          hero
          label="Revenue change, Q3 vs Q2"
          value={fmt(v('revenue_change_pct'), 'pct')}
          sub={<>Dashboard reports {fmt(v('revenue_change_pct_reported'), 'pct')}</>}
        />
        <KpiTile label="Q2 revenue" value={fmt(v('revenue_q2'), 'currency', { compact: true })} sub={fmt(v('revenue_q2'), 'currency')} />
        <KpiTile label="Q3 revenue" value={fmt(v('revenue_q3'), 'currency', { compact: true })} sub={fmt(v('revenue_q3'), 'currency')} />
        <KpiTile
          label="Sign-up growth"
          value={fmt(v('signup_growth_pct'), 'pct')}
          sub={
            <>
              {fmt(v('signups_q2'), 'count')} → {fmt(v('signups_q3'), 'count')} · dashboard{' '}
              {fmt(v('signup_growth_pct_reported'), 'pct')}
            </>
          }
        />
        <KpiTile
          label="30-day retention, recomputed"
          value={`${fmt(v('retention30_q2_independent'), 'rate')} → ${fmt(v('retention30_q3_independent'), 'rate')}`}
          sub={
            <>
              Dashboard: {fmt(v('retention30_q2_reported'), 'rate')} → {fmt(v('retention30_q3_reported'), 'rate')}
            </>
          }
        />
      </div>

      <div className="grid-2">
        <Card
          title="Main revenue drivers"
          subtitle="Central contribution in percentage points of Q2 revenue"
          actions={
            <a className="btn btn-ghost btn-sm" href={href('bridge')}>
              Explore bridge
            </a>
          }
        >
          <DriverList items={d.bridge} />
        </Card>
        <Card title="Initiative recommendations" subtitle="Shown only once the analysis supports a verdict">
          <ul className="initiative-list">
            {d.initiatives.map((i) => (
              <li key={i.initiative_id}>
                <a href={href(i.initiative_id === 'referral' ? 'referrals' : i.initiative_id)}>
                  <div className="il-head">
                    <span className="il-name">{i.name}</span>
                    <RecommendationBadge value={i.recommendation} />
                  </div>
                  <div className="il-meta">Launched {i.launched}</div>
                  <div className="il-text">{i.headline}</div>
                </a>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <ChartFrame
        title="Monthly revenue by region"
        subtitle={`${meta.currency} per month, ${monthLabel(months[0] ?? '', true)} – ${monthLabel(months[months.length - 1] ?? '', true)}. Shaded band: Q3.`}
        info={d.charts.overview_revenue_trend}
        legend={series.map((s) => ({ label: s.label, color: s.color, shape: 'line' as const }))}
        table={{
          columns: [
            { key: 'month', header: 'Month', render: (r) => monthLabel(String(r.month), true) },
            ...series.map((s) => ({ key: s.key, header: s.label, align: 'right' as const, render: (r: Record<string, unknown>) => fmt(r[s.key] as number, 'currency') })),
          ],
          rows: d.revenue_trend.rows,
        }}
      >
        <LineChart
          rows={d.revenue_trend.rows}
          xKey="month"
          series={series}
          unit="currency"
          xLabel={(m) => monthLabel(m)}
          tipLabel={(m) => monthLabel(m, true)}
          band={q3.length ? { from: q3[0], to: q3[q3.length - 1], label: 'Q3' } : undefined}
          ariaLabel="Monthly revenue by region"
        />
      </ChartFrame>

      <Card title="Confidence and caveats">
        {d.caveats.length ? (
          <ul className="caveats">
            {d.caveats.map((c) => (
              <li key={c}>
                <Icon name="info" size={15} />
                {c}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No caveats recorded.</p>
        )}
      </Card>
    </>
  )
}

function DriverList({ items }: { items: BridgeItem[] }) {
  const max = Math.max(...items.map((i) => Math.abs(i.central_pp)), 0.01)
  const sorted = [...items].sort((a, b) => Math.abs(b.central_pp) - Math.abs(a.central_pp))
  return (
    <ul className="driver-list">
      {sorted.map((i) => {
        const w = (Math.abs(i.central_pp) / max) * 50
        const cls = i.kind === 'unexplained' ? 'neutral' : i.central_pp >= 0 ? 'pos' : 'neg'
        return (
          <li key={i.position}>
            <span className="dl-label">{i.cause}</span>
            <span className="dl-track" aria-hidden="true">
              <span className="dl-zero" />
              <span
                className={`dl-bar ${cls}`}
                style={i.central_pp >= 0 ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }}
              />
            </span>
            <span className="dl-value">{fmt(i.central_pp, 'pp')}</span>
          </li>
        )
      })}
    </ul>
  )
}
