-- SQLite application schema.
--
-- This is the data contract between the analysis pipeline and the app.
-- Every data provider (mock today, the real assignment pipeline later) must
-- fill these tables; the backend and frontend only ever read them.
--
-- Unit conventions (column `unit` wherever it appears):
--   currency   amount in run_metadata.currency
--   rate       a proportion between 0 and 1 (displayed as %)
--   rate_diff  a difference between two rates, as a proportion (displayed as pp)
--   pct        a percentage change, already multiplied by 100 (e.g. -6.0)
--   pp         percentage points, already multiplied by 100
--   count      a whole number of things

PRAGMA foreign_keys = ON;

-- Key/value facts about the build: data_source ('mock' | 'assignment'),
-- data_label, generated_at, currency, as_of_date, period definitions, ...
CREATE TABLE run_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Provenance: every headline number points at the evidence that produced it.
CREATE TABLE evidence (
    evidence_id   TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    detail        TEXT NOT NULL,
    method        TEXT NOT NULL,
    source_tables TEXT NOT NULL
);

-- Headline numbers. basis = 'reported' (as stated in the brief/dashboards)
-- or 'independent' (recomputed by the pipeline). value NULL = not available.
CREATE TABLE kpi (
    kpi_id      TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    value       REAL,
    unit        TEXT NOT NULL CHECK (unit IN ('currency','rate','rate_diff','pct','pp','count')),
    period      TEXT,
    basis       TEXT NOT NULL CHECK (basis IN ('reported','independent')),
    note        TEXT,
    evidence_id TEXT REFERENCES evidence(evidence_id)
);

CREATE TABLE revenue_monthly (
    month            TEXT NOT NULL,          -- YYYY-MM
    region           TEXT NOT NULL,
    plan             TEXT NOT NULL,
    revenue          REAL NOT NULL,
    paying_customers INTEGER NOT NULL,
    PRIMARY KEY (month, region, plan)
);

-- Q2 -> Q3 revenue bridge. Central values must sum exactly to the
-- kpi 'revenue_change_pct' value (enforced by pipeline/validate.py).
CREATE TABLE bridge_item (
    position    INTEGER PRIMARY KEY,
    cause       TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('driver','unexplained')),
    central_pp  REAL NOT NULL,
    low_pp      REAL NOT NULL,
    high_pp     REAL NOT NULL,
    confidence  TEXT NOT NULL CHECK (confidence IN ('high','medium','low')),
    method      TEXT NOT NULL,
    evidence_id TEXT REFERENCES evidence(evidence_id),
    CHECK (low_pp <= central_pp AND central_pp <= high_pp)
);

-- The three initiatives. recommendation stays 'PENDING' until the analysis
-- of real data supports one; the app never shows an invented verdict.
CREATE TABLE initiative (
    initiative_id  TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    launched       TEXT NOT NULL,
    scope          TEXT NOT NULL,
    recommendation TEXT NOT NULL CHECK (recommendation IN ('KEEP','CHANGE','STOP','PENDING')),
    confidence     TEXT CHECK (confidence IN ('high','medium','low')),
    headline       TEXT NOT NULL,
    rationale      TEXT NOT NULL,
    monitoring     TEXT NOT NULL            -- newline-separated list
);

-- Summary metrics per initiative (pricing, referral, onboarding extras).
CREATE TABLE initiative_metric (
    initiative_id TEXT NOT NULL REFERENCES initiative(initiative_id),
    metric_id     TEXT NOT NULL,
    position      INTEGER NOT NULL,
    label         TEXT NOT NULL,
    value         REAL,
    low           REAL,
    high          REAL,
    unit          TEXT NOT NULL CHECK (unit IN ('currency','rate','rate_diff','pct','pp','count')),
    note          TEXT,
    PRIMARY KEY (initiative_id, metric_id)
);

CREATE TABLE experiment_arm (
    arm        TEXT PRIMARY KEY CHECK (arm IN ('control','treatment')),
    assigned   INTEGER NOT NULL,
    countries  TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL
);

-- Intention-to-treat effects, treatment minus control.
CREATE TABLE experiment_metric (
    metric_id       TEXT PRIMARY KEY,
    position        INTEGER NOT NULL,
    label           TEXT NOT NULL,
    unit            TEXT NOT NULL CHECK (unit IN ('rate','currency')),
    control_value   REAL NOT NULL,
    treatment_value REAL NOT NULL,
    effect          REAL NOT NULL,
    ci_low          REAL NOT NULL,
    ci_high         REAL NOT NULL,
    p_value         REAL,
    control_n       INTEGER NOT NULL,
    treatment_n     INTEGER NOT NULL,
    note            TEXT
);

CREATE TABLE price_point (
    plan           TEXT NOT NULL,
    region         TEXT NOT NULL,
    price_before   REAL NOT NULL,
    price_after    REAL NOT NULL,
    effective_date TEXT NOT NULL,
    PRIMARY KEY (plan, region)
);

CREATE TABLE pricing_monthly (
    month      TEXT NOT NULL,
    group_name TEXT NOT NULL,
    metric     TEXT NOT NULL CHECK (metric IN ('arppu','paid_conversion','churn','new_paid')),
    value      REAL NOT NULL,
    PRIMARY KEY (month, group_name, metric)
);

CREATE TABLE referral_funnel (
    position INTEGER PRIMARY KEY,
    stage    TEXT NOT NULL,
    count    INTEGER NOT NULL,
    note     TEXT
);

-- retained_rate NULL = cohort not yet mature at run_metadata.as_of_date.
CREATE TABLE retention_cohort (
    cohort_month  TEXT NOT NULL,
    segment       TEXT NOT NULL,
    day           INTEGER NOT NULL,
    cohort_size   INTEGER NOT NULL,
    retained_rate REAL,
    PRIMARY KEY (cohort_month, segment, day)
);

CREATE TABLE acquisition_weekly (
    week_start       TEXT NOT NULL,
    segment          TEXT NOT NULL,
    signups          INTEGER NOT NULL,
    paid_conversions INTEGER NOT NULL,
    PRIMARY KEY (week_start, segment)
);

CREATE TABLE dq_check (
    check_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    label    TEXT NOT NULL,
    status   TEXT NOT NULL CHECK (status IN ('pass','warn','fail','pending')),
    observed TEXT,
    expected TEXT,
    detail   TEXT
);

-- Dashboard figure vs. independently recomputed figure.
CREATE TABLE metric_reconciliation (
    metric_id         TEXT PRIMARY KEY,
    label             TEXT NOT NULL,
    unit              TEXT NOT NULL CHECK (unit IN ('currency','rate','rate_diff','pct','pp','count')),
    dashboard_value   REAL,
    independent_value REAL,
    status            TEXT NOT NULL CHECK (status IN ('match','mismatch','pending')),
    explanation       TEXT
);

CREATE TABLE metric_definition (
    metric_id  TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    definition TEXT NOT NULL,
    grain      TEXT NOT NULL,
    caveats    TEXT
);

-- Describes each chart so the analyst can explain it.
CREATE TABLE chart_catalog (
    chart_id      TEXT PRIMARY KEY,
    page          TEXT NOT NULL,
    title         TEXT NOT NULL,
    what_it_shows TEXT NOT NULL,
    how_to_read   TEXT NOT NULL,
    caveats       TEXT NOT NULL
);
