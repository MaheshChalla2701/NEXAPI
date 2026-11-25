import { useState } from 'react'
import type { InitiativeMetric, Meta, PricePoint, Pricing, Row } from '../api/types'
import { BarChart } from '../components/charts/BarChart'
import { ChartFrame } from '../components/charts/ChartFrame'
import { LineChart, type Series } from '../components/charts/LineChart'
import { InitiativeHeader } from '../components/InitiativeHeader'
import { PageData } from '../components/PageData'
import { DataTable } from '../components/ui/DataTable'
import { Card, Note, PageHeader, Segmented } from '../components/ui/Layout'
import { fmt, monthLabel, titleCase, type FormatUnit } from '../lib/format'

export function PricingPage() {
  return <PageData<Pricing> path="/api/pricing">{(d, meta) => <PricingView d={d} meta={meta} />}</PageData>
}

const GROUP_COLORS = ['var(--s1)', 'var(--s2)']

function PricingView({ d, meta }: { d: Pricing; meta: Meta }) {
  const plans = [...new Set(d.price_points.map((p) => p.plan))]
  const [plan, setPlan] = useState(plans[0] ?? 'monthly')
  const points = d.price_points.filter((p) => p.plan === plan)
  const series: Series[] = d.groups.map((g, i) => ({ key: g, label: g === 'Comparison' ? 'Comparison regions' : g, color: GROUP_COLORS[i % 2] }))
  const changeMonth = d.change_month?.slice(0, 7)
  const markers = changeMonth ? [{ x: changeMonth, label: 'Price change' }] : []
  const months = d.series.arppu.map((r) => String(r.month))
  const range = months.length ? `${monthLabel(months[0], true)} – ${monthLabel(months[months.length - 1], true)}` : ''

  const seriesTable = (rows: Row[], unit: FormatUnit) => ({
    columns: [
      { key: 'month', header: 'Month', render: (r: Row) => monthLabel(String(r.month), true) },
      ...series.map((s) => ({ key: s.key, header: s.label, align: 'right' as const, render: (r: Row) => fmt(r[s.key] as number, unit) })),
    ],
    rows,
  })

  const line = (rows: Row[], unit: FormatUnit, label: string, height = 240) => (
    <LineChart
      rows={rows}
      xKey="month"
      series={series}
      unit={unit}
      xLabel={(m) => monthLabel(m)}
      tipLabel={(m) => monthLabel(m, true)}
      markers={markers}
      height={height}
      ariaLabel={label}
    />
  )
  const legend = series.map((s) => ({ label: s.label, color: s.color, shape: 'line' as const }))

  return (
    <>
      <PageHeader
        eyebrow="Initiative 2"
        title="European price increase"
        description="Compares Europe with the other regions before and after the price change. The comparison is only meaningful if both groups were trending alike before it."
      />
      <InitiativeHeader initiative={d.initiative} isMock={meta.is_mock} />

      <ChartFrame
        title="List prices before and after the change"
        subtitle={`${meta.currency} per month, ${plan} plan. Effective ${d.change_month ?? '—'}.`}
        info={d.charts.pricing_price_points}
        legend={[
          { label: 'Before', color: 'var(--viz-neutral)' },
          { label: 'After', color: 'var(--s1)' },
        ]}
        table={{
          columns: [
            { key: 'region', header: 'Region' },
            { key: 'b', header: 'Before', align: 'right', render: (r: PricePoint) => fmt(r.price_before, 'currency') },
            { key: 'a', header: 'After', align: 'right', render: (r: PricePoint) => fmt(r.price_after, 'currency') },
          ],
          rows: points,
        }}
      >
        <div className="filter-row">
          <Segmented label="Plan" value={plan} onChange={setPlan} options={plans.map((p) => ({ value: p, label: titleCase(p) }))} />
        </div>
        <BarChart
          ariaLabel="List prices before and after by region"
          unit="currency"
          categories={points.map((p) => ({ key: p.region, label: p.region }))}
          series={[
            { key: 'before', label: 'Before', color: 'var(--viz-neutral)' },
            { key: 'after', label: 'After', color: 'var(--s1)' },
          ]}
          values={Object.fromEntries(points.map((p) => [p.region, { before: p.price_before, after: p.price_after }]))}
        />
      </ChartFrame>

      <ChartFrame
        title="Average revenue per paying customer"
        subtitle={`${meta.currency} per paying customer per month, ${range}`}
        info={d.charts.pricing_arppu}
        legend={legend}
        table={seriesTable(d.series.arppu, 'currency')}
      >
        {line(d.series.arppu, 'currency', 'ARPPU, Europe vs comparison regions', 260)}
      </ChartFrame>

      <div className="grid-2">
        <ChartFrame
          title="Paid conversion"
          subtitle={`Share of sign-ups converting to paid, ${range}`}
          info={d.charts.pricing_conversion}
          legend={legend}
          table={seriesTable(d.series.paid_conversion, 'rate')}
        >
          {line(d.series.paid_conversion, 'rate', 'Paid conversion, Europe vs comparison regions')}
        </ChartFrame>
        <ChartFrame
          title="Monthly churn"
          subtitle={`Share of paying customers lost per month, ${range}`}
          info={d.charts.pricing_churn}
          legend={legend}
          table={seriesTable(d.series.churn, 'rate')}
        >
          {line(d.series.churn, 'rate', 'Monthly churn, Europe vs comparison regions')}
        </ChartFrame>
      </div>

      <Card title="Before / after and difference-in-differences" subtitle="Ranges are shown where the data supports an uncertainty estimate">
        <DataTable<InitiativeMetric>
          rowKey={(r) => r.metric_id}
          columns={[
            { key: 'label', header: 'Measure', render: (r) => <strong>{r.label}</strong> },
            { key: 'value', header: 'Value', align: 'right', render: (r) => fmt(r.value, r.unit === 'currency' && r.metric_id.startsWith('did') ? 'currency_diff' : r.unit) },
            { key: 'range', header: 'Range', align: 'right', render: (r) => (r.low === null || r.high === null ? '—' : `${fmt(r.low, r.unit)} to ${fmt(r.high, r.unit)}`) },
            { key: 'note', header: 'Note', render: (r) => <span className="muted">{r.note ?? ''}</span> },
          ]}
          rows={d.metrics}
        />
      </Card>

      <Note>
        A before/after comparison mixes the price change with anything else that happened at the same time (according
        to the brief, the referral programme and the onboarding rollout both started on 1 Aug). Check pre-trends,
        grandfathered customers and renewal timing before attributing a change to price.
      </Note>
    </>
  )
}
