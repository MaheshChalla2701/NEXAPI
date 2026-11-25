import type { Bridge, BridgeItem, Meta } from '../api/types'
import { ChartFrame } from '../components/charts/ChartFrame'
import { WaterfallChart, type WaterfallItem } from '../components/charts/WaterfallChart'
import { PageData } from '../components/PageData'
import { ConfidenceBadge } from '../components/ui/Badges'
import { DataTable } from '../components/ui/DataTable'
import { Icon } from '../components/ui/Icon'
import { Card, KpiTile, PageHeader } from '../components/ui/Layout'
import { fmt, periodLabel } from '../lib/format'

export function BridgePage() {
  return <PageData<Bridge> path="/api/bridge">{(d, meta) => <BridgeView d={d} meta={meta} />}</PageData>
}

function BridgeView({ d, meta }: { d: Bridge; meta: Meta }) {
  const reconciled = Math.abs(d.reconciliation.difference_pp) < 1e-6
  const items: WaterfallItem[] = [
    ...d.items.map((i) => ({
      label: i.cause,
      value: i.central_pp,
      low: i.low_pp,
      high: i.high_pp,
      kind: i.kind,
      confidence: meta.is_mock ? 'not applicable (mock)' : i.confidence,
      detail: i.evidence_detail ?? undefined,
    })),
    { label: 'Total change, Q3 vs Q2', value: d.total.value ?? 0, kind: 'total' as const },
  ]

  return (
    <>
      <PageHeader
        eyebrow="Q2 → Q3"
        title="Revenue bridge"
        description={
          <>
            How each cause contributed to the change in revenue from Q2 ({periodLabel(meta.q2_period)}) to Q3 (
            {periodLabel(meta.q3_period)}), in percentage points of Q2 revenue. Whatever the identified causes do not
            explain is shown as its own bar.
          </>
        }
      />

      <div className="kpi-grid kpi-grid-3">
        <KpiTile hero label="Total revenue change" value={fmt(d.total.value, 'pct')} sub={d.total.period ?? undefined} />
        <KpiTile label="Sum of bridge bars" value={fmt(d.reconciliation.sum_central_pp, 'pp')} sub="Central estimates" />
        <KpiTile
          label="Reconciliation"
          value={reconciled ? 'Bars add up' : 'Does not reconcile'}
          sub={
            <span className={reconciled ? 'good-text' : 'critical-text'}>
              <Icon name={reconciled ? 'check' : 'x'} size={14} /> Difference {fmt(d.reconciliation.difference_pp, 'pp')}
            </span>
          }
        />
      </div>

      <ChartFrame
        title="Revenue bridge, Q2 to Q3"
        subtitle="Percentage points of Q2 revenue. Whiskers show each cause's low–high range."
        info={d.charts.bridge_waterfall}
        legend={[
          { label: 'Raises revenue', color: 'var(--viz-pos)' },
          { label: 'Lowers revenue', color: 'var(--viz-neg)' },
          { label: 'Unexplained', color: 'var(--viz-neutral)', shape: 'hatch' },
          { label: 'Total change', color: 'var(--viz-total)' },
          { label: 'Range', color: 'var(--text-2)', shape: 'whisker' },
        ]}
        table={{
          columns: [
            { key: 'label', header: 'Cause' },
            { key: 'value', header: 'Central', align: 'right', render: (r: WaterfallItem) => fmt(r.value, 'pp') },
            {
              key: 'range',
              header: 'Range',
              align: 'right',
              render: (r: WaterfallItem) => (r.low === undefined ? '—' : `${fmt(r.low, 'pp')} to ${fmt(r.high, 'pp')}`),
            },
          ],
          rows: items,
        }}
      >
        <WaterfallChart items={items} />
      </ChartFrame>

      <Card title="Evidence for each bar" subtitle="Method, confidence and the evidence record behind every contribution">
        <DataTable<BridgeItem>
          rowKey={(r) => String(r.position)}
          columns={[
            { key: 'cause', header: 'Cause', render: (r) => <strong>{r.cause}</strong> },
            { key: 'central_pp', header: 'Central', align: 'right', render: (r) => fmt(r.central_pp, 'pp') },
            { key: 'range', header: 'Low – high', align: 'right', render: (r) => `${fmt(r.low_pp, 'pp')} to ${fmt(r.high_pp, 'pp')}` },
            { key: 'confidence', header: 'Confidence', render: (r) => <ConfidenceBadge value={r.confidence} isMock={meta.is_mock} /> },
            { key: 'method', header: 'Method' },
            { key: 'evidence', header: 'Evidence', render: (r) => <span title={r.evidence_detail ?? ''}>{r.evidence_title ?? '—'}</span> },
          ]}
          rows={d.items}
        />
      </Card>

      {d.charts.bridge_waterfall && (
        <Card title="How to read the bridge">
          <p>{d.charts.bridge_waterfall.how_to_read}</p>
          <p className="muted">{d.charts.bridge_waterfall.caveats}</p>
        </Card>
      )}
    </>
  )
}
