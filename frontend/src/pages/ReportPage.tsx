import type { BridgeItem, Meta, Overview } from '../api/types'
import { PageData } from '../components/PageData'
import { ConfidenceBadge, RecommendationBadge, SourceBadge } from '../components/ui/Badges'
import { DataTable } from '../components/ui/DataTable'
import { Icon } from '../components/ui/Icon'
import { Card, KpiTile, Note, PageHeader } from '../components/ui/Layout'
import { dayLabel, fmt, periodLabel } from '../lib/format'
import { href } from '../lib/router'

export function ReportPage() {
  return <PageData<Overview> path="/api/overview">{(data, meta) => <ReportView data={data} meta={meta} />}</PageData>
}

function ReportView({ data, meta }: { data: Overview; meta: Meta }) {
  const value = (id: string) => data.kpis[id]?.value ?? null

  return (
    <>
      <PageHeader
        eyebrow="QUARTERLY REVIEW / REPORT"
        title="The quarter, in one place."
        description="A consolidated view of revenue, acquisition, retention and initiative status, with links to the supporting analysis."
        actions={<a className="btn btn-primary" href={href('decisions')}>View decisions</a>}
      />

      {meta.is_mock && (
        <Note tone="warning">
          <strong>Mock report.</strong> All figures below are synthetic development data. They demonstrate the report
          format and are not assignment findings, causal evidence or a basis for business decisions.
        </Note>
      )}

      <Card title="Reporting scope" actions={<SourceBadge isMock={meta.is_mock} />}>
        <p><strong>Q2:</strong> {periodLabel(meta.q2_period)} <strong>Q3:</strong> {periodLabel(meta.q3_period)}</p>
        <p className="muted">Source: {meta.data_label} ({meta.data_source}). Data as of {dayLabel(meta.as_of_date, true)}. Currency: {meta.currency}.</p>
      </Card>

      <div className="kpi-grid kpi-grid-3">
        <KpiTile
          hero
          label="Revenue change, Q3 vs Q2"
          value={fmt(value('revenue_change_pct'), 'pct')}
          sub={<>Q2 {fmt(value('revenue_q2'), 'currency')} / Q3 {fmt(value('revenue_q3'), 'currency')}</>}
        />
        <KpiTile
          label="Sign-up growth"
          value={fmt(value('signup_growth_pct'), 'pct')}
          sub={<>Q2 {fmt(value('signups_q2'), 'count')} / Q3 {fmt(value('signups_q3'), 'count')}</>}
        />
        <KpiTile
          label="Q3 retention, recomputed"
          value={fmt(value('retention30_q3_independent'), 'rate')}
          sub={<>30-day retention / Q2 {fmt(value('retention30_q2_independent'), 'rate')}</>}
        />
      </div>

      <Card
        title="Revenue bridge summary"
        subtitle={`${meta.is_mock ? 'Illustrative contributions' : 'Recorded contributions'} in percentage points of Q2 revenue. Low and high values show the recorded range.`}
        actions={<a className="btn btn-ghost btn-sm" href={href('bridge')}>Explore revenue bridge</a>}
      >
        {data.bridge.length ? (
          <DataTable<BridgeItem>
            caption="Revenue bridge contributions and confidence"
            rowKey={(row) => String(row.position)}
            columns={[
              { key: 'cause', header: 'Contribution', render: (row) => <strong>{row.cause}</strong> },
              { key: 'central_pp', header: 'Central', align: 'right', render: (row) => fmt(row.central_pp, 'pp') },
              { key: 'range', header: 'Low to high', align: 'right', render: (row) => `${fmt(row.low_pp, 'pp')} to ${fmt(row.high_pp, 'pp')}` },
              { key: 'confidence', header: 'Confidence', render: (row) => <ConfidenceBadge value={row.confidence} isMock={meta.is_mock} /> },
              { key: 'method', header: 'Method' },
            ]}
            rows={data.bridge}
          />
        ) : <p className="muted">No bridge contributions are available for this report.</p>}
      </Card>

      <div className="grid-2">
        <Card
          title="Initiative status"
          subtitle={meta.is_mock ? 'Sample statuses; recommendations await real analysis' : 'Recommendations recorded in the current analysis'}
          actions={<a className="btn btn-ghost btn-sm" href={href('decisions')}>Decision details</a>}
        >
          {data.initiatives.length ? (
            <ul className="initiative-list">
              {data.initiatives.map((initiative) => (
                <li key={initiative.initiative_id}>
                  <a href={href(initiative.initiative_id === 'referral' ? 'referrals' : initiative.initiative_id)}>
                    <div className="il-head">
                      <span className="il-name">{initiative.name}</span>
                      <RecommendationBadge value={initiative.recommendation} />
                    </div>
                    <div className="il-meta">Launched {initiative.launched}</div>
                    <div className="il-text">{initiative.headline}</div>
                  </a>
                </li>
              ))}
            </ul>
          ) : <p className="muted">No initiatives are available for this report.</p>}
        </Card>

        <Card title="Confidence and limitations">
          {data.caveats.length ? (
            <ul className="caveats">
              {data.caveats.map((caveat) => (
                <li key={caveat}><Icon name="info" size={15} />{caveat}</li>
              ))}
            </ul>
          ) : <p className="muted">No caveats are recorded in the current data.</p>}
          <p><a href={href('data-quality')}>Review data quality and metric reconciliation</a></p>
          <p><a href={href('retention')}>Explore retention and acquisition</a></p>
        </Card>
      </div>
    </>
  )
}
