import type { Initiative, Meta, Overview } from '../api/types'
import { PageData } from '../components/PageData'
import { ConfidenceBadge, RecommendationBadge } from '../components/ui/Badges'
import { Card, KpiTile, Note, PageHeader } from '../components/ui/Layout'
import { fmt, periodLabel } from '../lib/format'
import { href } from '../lib/router'

const REVIEW_STEPS: Record<Initiative['initiative_id'], string[]> = {
  onboarding: [
    'Check assignment balance and sample-ratio checks before interpreting the experiment.',
    'Review conversion and revenue effects with their confidence intervals and retention guardrails.',
  ],
  pricing: [
    'Compare European ARPPU, paid conversion and churn with the comparison group.',
    'Review the before-and-after and difference-in-differences evidence, including regional mix changes.',
  ],
  referral: [
    'Reconcile the referral funnel and rewards owed versus paid before assessing acquisition cost.',
    'Check incrementality and referred-customer retention before attributing growth to the programme.',
  ],
}

export function DecisionsPage() {
  return <PageData<Overview> path="/api/overview">{(d, meta) => <DecisionsView d={d} meta={meta} />}</PageData>
}

function DecisionsView({ d, meta }: { d: Overview; meta: Meta }) {
  const value = (id: string) => d.kpis[id]?.value ?? null

  return (
    <>
      <PageHeader
        eyebrow="QUARTERLY REVIEW / INITIATIVES"
        title="Decisions"
        description={`Review the recorded recommendations, their rationale and the evidence to inspect across Q2 (${periodLabel(meta.q2_period)}) and Q3 (${periodLabel(meta.q3_period)}).`}
        actions={<a className="btn" href={href('data-quality')}>Review data quality</a>}
      />

      {meta.is_mock && (
        <Note tone="warning">
          <strong>Mock decision workspace.</strong> These figures and initiative details are synthetic.
          Pending recommendations are not business decisions; the proposed review steps below describe
          what to examine when real evidence is available.
        </Note>
      )}

      <div className="kpi-grid kpi-grid-3">
        <KpiTile
          hero
          label="Revenue change, Q3 vs Q2"
          value={fmt(value('revenue_change_pct'), 'pct')}
          sub={<>Q3 revenue: {fmt(value('revenue_q3'), 'currency', { compact: true })}</>}
        />
        <KpiTile
          label="Sign-up growth"
          value={fmt(value('signup_growth_pct'), 'pct')}
          sub={<>Q3 sign-ups: {fmt(value('signups_q3'), 'count')}</>}
        />
        <KpiTile
          label="Q3 30-day retention, recomputed"
          value={fmt(value('retention30_q3_independent'), 'rate')}
          sub={<>Q2: {fmt(value('retention30_q2_independent'), 'rate')}</>}
        />
      </div>

      <Note>
        These overview metrics provide quarterly context. They do not establish the causal effect of
        an individual initiative. Each recommendation below is the status recorded in the current data.
      </Note>

      {d.initiatives.length ? d.initiatives.map((initiative) => (
        <Card
          key={initiative.initiative_id}
          title={initiative.name}
          subtitle={initiative.scope}
          actions={
            <>
              <RecommendationBadge value={initiative.recommendation} />
              <ConfidenceBadge value={initiative.confidence} isMock={meta.is_mock} />
            </>
          }
        >
          <p className="initiative-headline">{initiative.headline}</p>
          <p>{initiative.rationale || 'No rationale has been recorded for this initiative.'}</p>
          <p className="muted small">Launched {initiative.launched}</p>

          <div className="answer-section">
            <h3 className="section-title">Proposed evidence review</h3>
            <ul>
              {REVIEW_STEPS[initiative.initiative_id].map((step) => <li key={step}>{step}</li>)}
            </ul>
          </div>

          {initiative.monitoring.length > 0 && (
            <div className="answer-section">
              <h3 className="section-title">Recorded monitoring plan</h3>
              <ul>{initiative.monitoring.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}

          <div className="answer-section">
            <a className="btn btn-sm" href={href(initiative.initiative_id === 'referral' ? 'referrals' : initiative.initiative_id)}>
              Review initiative evidence
            </a>
          </div>
        </Card>
      )) : (
        <Card title="No initiative decisions recorded">
          <p className="muted">Recommendations will appear here when initiatives are available in the current dataset.</p>
        </Card>
      )}

      <Card title="Review limitations" subtitle="Caveats recorded with the current overview">
        {d.caveats.length ? (
          <ul className="caveats">{d.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}</ul>
        ) : (
          <p className="muted">No caveats have been recorded. This does not establish that the evidence is complete.</p>
        )}
      </Card>
    </>
  )
}
