"""Every parameter of the SYNTHETIC dataset, with where it comes from.

Kinds:
  brief       stated in the assignment brief (used as given)
  assumption  chosen by us to make a plausible small-business SaaS; not in the brief
  scenario    deliberate scenario design (a cause or a data problem the analysis should be able to find)
  calibrated  solved numerically by the generator so the brief's reported figure holds
  scale       size limits chosen to respect the brief's 4 GB RAM / nearly-full disk constraint

data/ASSUMPTIONS.md is generated from this list, so code and documentation cannot drift apart.
Only one value is calibrated: `promo_annual_share`, tuned so the revenue dashboard shows -6.0%.
A few volume/behaviour assumptions (referral volume, email click rate, activity decay) were chosen so the
synthetic dashboards land near the brief's other reported figures (+22% sign-ups, 41% -> 52% retention);
those are approximate by design and are NOT solved for. Every initiative outcome follows from these inputs.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class Assumption:
    key: str
    value: object
    kind: str
    description: str


D = dt.date

ASSUMPTIONS: list[Assumption] = [
    # ---- calendar -------------------------------------------------------------------------------
    Assumption("seed", 20260930, "assumption", "Master random seed; same seed gives byte-identical files."),
    Assumption("sim_start", D(2025, 1, 1), "assumption", "First day simulated (sign-ups, billing)."),
    Assumption("q2", (D(2026, 4, 1), D(2026, 6, 30)), "assumption", "Q2 = calendar Q2 2026, UTC. The brief names no year."),
    Assumption("q3", (D(2026, 7, 1), D(2026, 9, 30)), "assumption", "Q3 = calendar Q3 2026, UTC."),
    Assumption("extract_date", D(2026, 10, 5), "assumption",
               "Data extracted on this date: September cohorts are not yet 30 days old."),
    Assumption("events_from", D(2026, 2, 1), "scale",
               "Product events are generated only for workspaces created on/after this date (cohort window)."),
    # ---- the three initiatives (facts from the brief) -------------------------------------------
    Assumption("onboarding_test_countries", ("US", "CA"), "assumption",
               "Brief: randomized test in two countries. Which two is our choice."),
    Assumption("onboarding_test_window", (D(2026, 6, 1), D(2026, 7, 15)), "assumption",
               "Test window (brief gives none). 50/50 random assignment at workspace creation."),
    Assumption("onboarding_global_launch", D(2026, 8, 1), "brief", "New onboarding flow launched everywhere on 1 August."),
    Assumption("price_increase_date", D(2026, 9, 1), "brief", "Europe price increase effective 1 September."),
    Assumption("price_increase_pct", 0.15, "brief", "Europe price increase: 15%."),
    Assumption("referral_launch", D(2026, 8, 1), "brief", "Partner referral programme launched 1 August."),
    # ---- market & product -------------------------------------------------------------------------
    Assumption("organic_signups_per_day_start", 98.0, "assumption", "Organic sign-ups per day in Jan 2025."),
    Assumption("organic_growth_per_month", 0.012, "assumption", "Underlying organic sign-up growth per month."),
    Assumption("signup_seasonality", {1: 1.0, 2: 1.02, 3: 1.04, 4: 1.03, 5: 1.0, 6: 0.98, 7: 0.93, 8: 0.9,
                                       9: 1.02, 10: 1.05, 11: 1.02, 12: 0.85}, "assumption",
               "Monthly sign-up seasonality (summer dip, December dip)."),
    Assumption("weekend_factor", 0.55, "assumption", "Sign-ups on Sat/Sun relative to weekdays."),
    Assumption("initial_paying_customers", 8200, "assumption",
               "Paying customers already on the books on sim_start (their older workspaces are included)."),
    Assumption("prices_monthly", {"USD": {"starter": 15.0, "team": 39.0}, "EUR": {"starter": 14.0, "team": 36.0},
                                  "GBP": {"starter": 12.0, "team": 31.0}}, "assumption",
               "Monthly list prices per workspace. Annual plan = 10x monthly, paid upfront."),
    Assumption("price_increase_currencies", ("EUR", "GBP"), "assumption",
               "'Europe' = customers billed in EUR or GBP (EU countries + UK)."),
    Assumption("existing_customer_price_rule", "new price from first renewal on/after 2026-10-01", "assumption",
               "Existing European customers keep the old price until their first renewal on/after 1 Oct "
               "(30 days' notice, emailed 15 Aug). New European subscriptions from 1 Sep pay the new price."),
    Assumption("price_notice_date", D(2026, 8, 15), "assumption", "Date existing European customers were notified."),
    Assumption("annual_share", 0.22, "assumption", "Share of new paying customers choosing the annual plan."),
    Assumption("team_share", 0.35, "assumption", "Share choosing the Team tier (0.6 for 6+ person companies)."),
    # ---- funnel -----------------------------------------------------------------------------------
    Assumption("activation_base", 0.36, "assumption",
               "P(activation within 7 days) with the old onboarding. Activation = project created AND teammate invited."),
    Assumption("activation_size_effect", {"1-5": 0.0, "6-20": 0.05, "21-50": 0.08}, "assumption",
               "Added activation probability by company size."),
    Assumption("onboarding_v2_activation_lift", 0.06, "scenario",
               "TRUE effect of the new onboarding flow: +6 pp activation. It has no direct effect on conversion."),
    Assumption("onboarding_v2_reminder_emails", (2, 5, 10, 20, 28), "scenario",
               "New flow sends reminder emails on these days; a click is logged as an 'onboarding_email_clicked' event."),
    Assumption("email_click_rate", 0.06, "scenario", "P(click) per reminder email."),
    Assumption("activity_daily_prob", {"paying": 0.55, "activated": (0.33, 18), "not_activated": (0.02, 5)},
               "assumption", "P(any product activity on day d): paying customers flat; others a*exp(-d/tau)."),
    Assumption("conversion_if_activated", 0.30, "assumption", "P(paid within 30 days | activated)."),
    Assumption("conversion_if_not_activated", 0.025, "assumption", "P(paid within 30 days | not activated)."),
    Assumption("price_elasticity_new_customers", 1.3, "assumption",
               "Conversion of new European sign-ups after 1 Sep is multiplied by 1.15^-1.3 (about 0.83)."),
    # ---- retention & billing ----------------------------------------------------------------------
    Assumption("monthly_churn", 0.032, "assumption", "Voluntary churn per monthly renewal (tenure > 3 months)."),
    Assumption("monthly_churn_early", 0.06, "assumption", "Voluntary churn at renewals 1-3."),
    Assumption("annual_nonrenewal", 0.22, "assumption", "P(annual customer does not renew)."),
    Assumption("price_notice_churn_multiplier", 1.8, "scenario",
               "European monthly customers renewing 15 Aug - 30 Sep churn 1.8x (reaction to the notice); "
               "annual non-renewal x1.3."),
    Assumption("payment_fail_rate_before", 0.035, "assumption", "P(first charge attempt fails) before 1 Jul 2026."),
    Assumption("payment_fail_rate_after", 0.075, "scenario",
               "P(first attempt fails) from 1 Jul 2026: an unannounced payment-processor migration. "
               "Not mentioned in the brief; a non-initiative cause the analysis should be able to find."),
    Assumption("payment_retry_success", (0.5, 0.4), "assumption",
               "Success of retry 2 (+3 days) and retry 3 (+7 days). If all fail, the subscription ends."),
    Assumption("refund_rate_monthly", 0.012, "assumption", "Share of monthly charges refunded within 14 days."),
    Assumption("refund_rate_first_annual", 0.04, "assumption",
               "Share of first annual charges refunded within 14 days (subscription then cancelled)."),
    # ---- annual promotion (the calibrated lever) ---------------------------------------------------
    Assumption("promo_window", (D(2025, 4, 1), D(2025, 6, 30)), "scenario",
               "Q2 2025 promotion: annual plans 20% off in year one. Renewals fall in Q2 2026 at full price."),
    Assumption("promo_discount", 0.20, "scenario", "Promotion discount on the first annual payment."),
    Assumption("promo_annual_share", None, "calibrated",
               "Share of Q2-2025 converters taking the annual plan. Solved so that the revenue dashboard "
               "(dashboards/revenue.sql) shows Q3 vs Q2 = -6.0%. Its value is written to data/MANIFEST.json."),
    Assumption("revenue_target_pct", -6.0, "brief", "Q3 revenue fell 6.0% against Q2 (dashboard figure)."),
    # ---- referral programme ----------------------------------------------------------------------
    Assumption("referral_signups_per_day", 55.0, "assumption",
               "Referred sign-ups per day once ramped (2-week ramp from launch). Brief gives no volume."),
    Assumption("referral_partners", 60, "assumption", "Number of active partners (heavy-tailed volumes)."),
    Assumption("referral_cannibalised_share", 0.30, "scenario",
               "Average share of referred sign-ups who would have signed up organically anyway (varies by partner). "
               "Organic sign-ups are reduced by the same amount: they are not incremental."),
    Assumption("referral_low_intent_activation_mult", 0.45, "scenario",
               "Incremental referred workspaces are low-intent: activation x0.45, conversion x0.6, churn x1.7."),
    Assumption("referral_partner_sync_events", 0.6, "scenario",
               "P(partner automation logs 'partner_sync' events in a referred workspace's first 30 days)."),
    Assumption("referral_payout_usd", 50.0, "assumption",
               "Payout per referral record (brief: partners paid per new workspace; amount not given)."),
    Assumption("referral_duplicate_claims", 0.05, "scenario", "Share of referral records duplicated under a second partner."),
    Assumption("referral_preexisting_claims", 0.08, "scenario",
               "Extra referral records (as a share of referrals) that point to workspaces created long before the referral."),
    Assumption("referral_existing_owner_share", 0.08, "scenario",
               "Share of incremental referred workspaces whose owner already has another workspace (same owner hash)."),
    # ---- data-quality problems planted in the files -------------------------------------------------
    Assumption("dq_duplicate_payment_rows", 0.004, "scenario", "Share of successful charges exported twice (same payment_id)."),
    Assumption("dq_missing_event_day", D(2026, 8, 17), "scenario", "This day's event file is missing (pipeline outage)."),
    Assumption("dq_late_event_share", 0.015, "scenario", "Share of events landing in the next day's file."),
    Assumption("dq_experiment_duplicate_rows", 0.006, "scenario", "Share of experiment assignments logged twice."),
    Assumption("dq_experiment_missing_day", D(2026, 6, 21), "scenario", "Experiment assignment log lost for this day."),
    # ---- scale -----------------------------------------------------------------------------------
    Assumption("events_scale_note", "about 1M rows instead of ~20M", "scale",
               "Events are generated at roughly 1/20 of the brief's volume so generation and analysis fit "
               "comfortably in 4 GB RAM and a nearly-full disk; daily files are gzip-compressed CSV."),
]

P: dict[str, object] = {a.key: a.value for a in ASSUMPTIONS}

COUNTRIES = [
    # code, weight, currency, europe
    ("US", 0.30, "USD", False), ("GB", 0.08, "GBP", True), ("DE", 0.09, "EUR", True), ("FR", 0.07, "EUR", True),
    ("NL", 0.04, "EUR", True), ("ES", 0.04, "EUR", True), ("IT", 0.04, "EUR", True), ("SE", 0.02, "EUR", True),
    ("PL", 0.02, "EUR", True), ("CA", 0.07, "USD", False), ("AU", 0.05, "USD", False), ("IN", 0.08, "USD", False),
    ("BR", 0.05, "USD", False), ("JP", 0.03, "USD", False), ("MX", 0.02, "USD", False),
]

# Monthly FX, USD per unit of currency (assumption: gentle drift, no shocks).
def fx_usd_per_unit(currency: str, year: int, month: int) -> float:
    if currency == "USD":
        return 1.0
    i = (year - 2025) * 12 + (month - 1)
    if currency == "EUR":
        return round(1.04 + 0.0035 * i + 0.004 * ((i * 7) % 5 - 2), 4)
    if currency == "GBP":
        return round(1.25 + 0.002 * i + 0.003 * ((i * 3) % 5 - 2), 4)
    raise ValueError(currency)
