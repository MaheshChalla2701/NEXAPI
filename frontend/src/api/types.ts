// Shapes returned by the Python API (backend/api.py). The frontend never
// computes business metrics; it only formats and draws these values.

export type Unit = 'currency' | 'rate' | 'rate_diff' | 'pct' | 'pp' | 'count'
export type Confidence = 'high' | 'medium' | 'low'
export type Recommendation = 'KEEP' | 'CHANGE' | 'STOP' | 'PENDING'
export type CheckStatus = 'pass' | 'warn' | 'fail' | 'pending'
export type Row = Record<string, string | number | null>

export interface Meta {
  data_source: string
  is_mock: boolean
  data_label: string
  currency: string
  as_of_date: string
  q2_period: string
  q3_period: string
  generated_at: string
}

export interface Envelope<T> {
  meta: Meta
  data: T
}

export interface Kpi {
  kpi_id: string
  label: string
  value: number | null
  unit: Unit
  period: string | null
  basis: 'reported' | 'independent'
  note: string | null
  evidence_id: string | null
}

export interface ChartInfo {
  chart_id: string
  page: string
  title: string
  what_it_shows: string
  how_to_read: string
  caveats: string
}
export type Charts = Record<string, ChartInfo>

export interface BridgeItem {
  position: number
  cause: string
  kind: 'driver' | 'unexplained'
  central_pp: number
  low_pp: number
  high_pp: number
  confidence: Confidence
  method: string
  evidence_id: string | null
  evidence_title: string | null
  evidence_detail: string | null
}

export interface Initiative {
  initiative_id: 'onboarding' | 'pricing' | 'referral'
  name: string
  launched: string
  scope: string
  recommendation: Recommendation
  confidence: Confidence | null
  headline: string
  rationale: string
  monitoring: string[]
}

export interface InitiativeMetric {
  metric_id: string
  label: string
  value: number | null
  low: number | null
  high: number | null
  unit: Unit
  note: string | null
}

export interface Evidence {
  evidence_id: string
  title: string
  detail: string
  method: string
  source_tables: string
}

export interface DqCheck {
  check_id: string
  category: string
  label: string
  status: CheckStatus
  observed: string | null
  expected: string | null
  detail: string | null
}

export interface Definition {
  metric_id: string
  name: string
  definition: string
  grain: string
  caveats: string | null
}

export interface Overview {
  kpis: Record<string, Kpi>
  bridge: BridgeItem[]
  initiatives: Initiative[]
  caveats: string[]
  revenue_trend: { regions: string[]; rows: Row[] }
  charts: Charts
}

export interface Bridge {
  items: BridgeItem[]
  total: Kpi
  reconciliation: { sum_central_pp: number; total_pp: number; difference_pp: number }
  evidence: Evidence[]
  charts: Charts
}

export interface ExperimentArm {
  arm: 'control' | 'treatment'
  assigned: number
  countries: string
  start_date: string
  end_date: string
}

export interface ExperimentMetric {
  metric_id: string
  position: number
  label: string
  unit: 'rate' | 'currency'
  control_value: number
  treatment_value: number
  effect: number
  ci_low: number
  ci_high: number
  p_value: number | null
  control_n: number
  treatment_n: number
  note: string | null
}

export interface Onboarding {
  initiative: Initiative
  arms: ExperimentArm[]
  metrics: ExperimentMetric[]
  checks: DqCheck[]
  charts: Charts
}

export interface PricePoint {
  plan: string
  region: string
  price_before: number
  price_after: number
  effective_date: string
}

export interface Pricing {
  initiative: Initiative
  price_points: PricePoint[]
  groups: string[]
  series: Record<'arppu' | 'paid_conversion' | 'churn' | 'new_paid', Row[]>
  metrics: InitiativeMetric[]
  change_month: string | null
  charts: Charts
}

export interface FunnelStage {
  position: number
  stage: string
  count: number
  note: string | null
}

export interface Referrals {
  initiative: Initiative
  funnel: FunnelStage[]
  metrics: InitiativeMetric[]
  weekly_signups: Row[]
  charts: Charts
}

export interface Cohort {
  cohort_month: string
  cohort_size: number
  rates: Record<string, number | null>
}

export interface Retention {
  segment: string
  segments: string[]
  days: number[]
  cohorts: Cohort[]
  acquisition: Row[]
  kpis: Record<string, Kpi>
  definitions: Definition[]
  charts: Charts
}

export interface ReconciliationRow {
  metric_id: string
  label: string
  unit: Unit
  dashboard_value: number | null
  independent_value: number | null
  status: 'match' | 'mismatch' | 'pending'
  explanation: string | null
  difference: number | null
}

export interface DataQuality {
  summary: Record<CheckStatus, number>
  checks: DqCheck[]
  reconciliation: ReconciliationRow[]
  definitions: Definition[]
  charts: Charts
}

export interface AnalystStatus {
  default_mode: 'local' | 'external'
  external_enabled: boolean
  external_configured: boolean
  external_provider: string | null
  external_model: string | null
}

export interface MetaResponse {
  meta: Meta
  analyst: AnalystStatus
}

export interface AnalystEvidence {
  label: string
  value: string
  source: string
}

export interface AnalystAnswer {
  intent: string
  title: string
  summary: string[]
  evidence: AnalystEvidence[]
  confidence: string
  limitations: string[]
  next_actions: string[]
  related: string[]
  answered: boolean
  data_source: string
  notices: string[]
  mode: 'local' | 'external'
  provider?: string
  model?: string
}

export interface Suggestion {
  question: string
  intent: string
}
