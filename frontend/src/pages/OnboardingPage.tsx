import type { ExperimentMetric, Meta, Onboarding } from '../api/types'
import { BarChart } from '../components/charts/BarChart'
import { ChartFrame } from '../components/charts/ChartFrame'
import { IntervalPlot } from '../components/charts/IntervalPlot'
import { InitiativeHeader } from '../components/InitiativeHeader'
import { PageData } from '../components/PageData'
import { StatusBadge } from '../components/ui/Badges'
import { DataTable } from '../components/ui/DataTable'
import { Card, KpiTile, Note, PageHeader } from '../components/ui/Layout'
import { dayLabel, fmt } from '../lib/format'

export function OnboardingPage() {
  return <PageData<Onboarding> path="/api/onboarding">{(d, meta) => <OnboardingView d={d} meta={meta} />}</PageData>
}

function plainP(p: number | null): string {
  if (p === null) return 'No test available.'
  if (p < 0.001) return 'Very unlikely to be chance alone (p < 0.001).'
  return `With no real effect, a gap this large would appear about ${Math.round(p * 100)}% of the time by chance (p = ${p.toFixed(3)}).`
}

function OnboardingView({ d, meta }: { d: Onboarding; meta: Meta }) {
  const control = d.arms.find((a) => a.arm === 'control')
  const treatment = d.arms.find((a) => a.arm === 'treatment')
  const rates = d.metrics.filter((m) => m.unit === 'rate')
  const srm = d.checks.find((c) => c.check_id === 'exp_srm')
  const effectUnit = (m: ExperimentMetric) => (m.unit === 'rate' ? 'rate_diff' : 'currency_diff') as 'rate_diff' | 'currency_diff'

  return (
    <>
      <PageHeader
        eyebrow="Initiative 1"
        title="New onboarding flow"
        description="Randomized test of the new flow against the old one. Effects are intention-to-treat: every workspace counts in the arm it was assigned to, whether or not it saw the flow."
      />
      <InitiativeHeader initiative={d.initiative} isMock={meta.is_mock} />

      <div className="kpi-grid">
        <KpiTile label="Control workspaces" value={fmt(control?.assigned, 'count')} sub="Old onboarding" />
        <KpiTile label="Treatment workspaces" value={fmt(treatment?.assigned, 'count')} sub="New onboarding" />
        <KpiTile label="Countries" value={String(control?.countries.split(',').length ?? '—')} sub={control?.countries} />
        <KpiTile
          label="Test window"
          value={control ? `${dayLabel(control.start_date)} – ${dayLabel(control.end_date)}` : '—'}
          sub={control ? control.start_date.slice(0, 4) : undefined}
        />
        <KpiTile
          label="Sample split check"
          value={srm ? (srm.status === 'pass' ? 'Balanced' : 'Check split') : '—'}
          sub={srm ? <StatusBadge value={srm.status} /> : undefined}
        />
      </div>

      <div className="grid-2">
        <ChartFrame
          title="Treatment effect on each rate"
          subtitle="Treatment minus control, percentage points, with 95% intervals"
          info={d.charts.onboarding_effects}
          legend={[
            { label: 'Clearly higher', color: 'var(--viz-pos)', shape: 'whisker' },
            { label: 'Clearly lower', color: 'var(--viz-neg)', shape: 'whisker' },
            { label: 'Could be zero', color: 'var(--viz-neutral)', shape: 'whisker' },
          ]}
          table={{
            columns: [
              { key: 'label', header: 'Metric' },
              { key: 'effect', header: 'Effect', align: 'right', render: (r: ExperimentMetric) => fmt(r.effect, 'rate_diff') },
              { key: 'ci', header: '95% interval', align: 'right', render: (r: ExperimentMetric) => `${fmt(r.ci_low, 'rate_diff')} to ${fmt(r.ci_high, 'rate_diff')}` },
            ],
            rows: rates,
          }}
        >
          <IntervalPlot
            unit="rate_diff"
            ariaLabel="Treatment effects with 95% intervals"
            rows={rates.map((m) => ({ label: m.label, effect: m.effect, low: m.ci_low, high: m.ci_high, detail: plainP(m.p_value) }))}
          />
        </ChartFrame>

        <ChartFrame
          title="Outcome rates by arm"
          subtitle="Share of assigned workspaces reaching each outcome"
          info={d.charts.onboarding_rates}
          legend={[
            { label: 'Control', color: 'var(--s1)' },
            { label: 'Treatment', color: 'var(--s2)' },
          ]}
          table={{
            columns: [
              { key: 'label', header: 'Metric' },
              { key: 'control_value', header: 'Control', align: 'right', render: (r: ExperimentMetric) => fmt(r.control_value, 'rate') },
              { key: 'treatment_value', header: 'Treatment', align: 'right', render: (r: ExperimentMetric) => fmt(r.treatment_value, 'rate') },
            ],
            rows: rates,
          }}
        >
          <BarChart
            ariaLabel="Outcome rates for control and treatment"
            unit="rate"
            categories={rates.map((m) => ({ key: m.metric_id, label: m.label.replace('30-day ', '30d ') }))}
            series={[
              { key: 'control', label: 'Control', color: 'var(--s1)' },
              { key: 'treatment', label: 'Treatment', color: 'var(--s2)' },
            ]}
            values={Object.fromEntries(rates.map((m) => [m.metric_id, { control: m.control_value, treatment: m.treatment_value }]))}
          />
        </ChartFrame>
      </div>

      <Card title="All experiment results" subtitle="Intention-to-treat estimates with 95% intervals and a plain-language reading of each test">
        <DataTable<ExperimentMetric>
          rowKey={(r) => r.metric_id}
          columns={[
            { key: 'label', header: 'Metric', render: (r) => <strong>{r.label}</strong> },
            { key: 'c', header: 'Control', align: 'right', render: (r) => fmt(r.control_value, r.unit) },
            { key: 't', header: 'Treatment', align: 'right', render: (r) => fmt(r.treatment_value, r.unit) },
            { key: 'e', header: 'Effect', align: 'right', render: (r) => fmt(r.effect, effectUnit(r)) },
            { key: 'ci', header: '95% interval', align: 'right', render: (r) => `${fmt(r.ci_low, effectUnit(r))} to ${fmt(r.ci_high, effectUnit(r))}` },
            { key: 'p', header: 'What the test says', render: (r) => <span className="muted">{plainP(r.p_value)}</span> },
          ]}
          rows={d.metrics}
        />
      </Card>

      {srm && (
        <Card title="Experiment integrity">
          <div className="check-line">
            <StatusBadge value={srm.status} />
            <div>
              <strong>{srm.label}</strong>
              <div className="muted">{srm.observed}</div>
              <div className="muted small">{srm.detail}</div>
            </div>
          </div>
        </Card>
      )}

      <Note>
        A statistically clear effect is not automatically a large one: compare the size of each effect with what it is
        worth in revenue. A test in two countries may also not carry over to every market after the global rollout.
      </Note>
    </>
  )
}
