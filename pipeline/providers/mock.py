"""MOCK data provider - synthetic values for developing the app only.

Nothing produced here is a finding about the assignment. Every value is drawn
from a seeded random generator so the build is deterministic, and every table
is tagged through run_metadata.data_source = 'mock', which the API and the UI
surface on every page.

Deliberate choices that keep mock output from looking like conclusions:
  * initiative recommendations are always PENDING - no KEEP/CHANGE/STOP;
  * bridge drivers are prefixed "Mock ·" and sized at random;
  * the mock revenue change is whatever the random series produce, not -6.0%.

The only brief-derived facts used are launch dates/scope of the initiatives,
which are inputs from the brief, not results.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, datetime, timedelta, timezone

from pipeline import stats

NAME = "mock"
DEFAULT_SEED = 20260701

YEAR = 2026
MONTHS = [f"{YEAR}-{m:02d}" for m in range(1, 10)]
Q2_MONTHS = MONTHS[3:6]
Q3_MONTHS = MONTHS[6:9]
REGIONS = ["Europe", "North America", "APAC", "Rest of world"]
PLANS = ["monthly", "annual"]
AS_OF = date(YEAR, 9, 30)
RETENTION_DAYS = [7, 14, 30, 60, 90]
REFERRAL_START = date(YEAR, 8, 1)


def populate(conn: sqlite3.Connection, options: dict) -> None:
    seed = int(options.get("seed", DEFAULT_SEED))
    rng = random.Random(seed)

    _metadata(conn, seed)
    _evidence(conn)
    revenue = _revenue(rng, conn)
    acquisition = _acquisition(rng, conn)
    retention = _retention(rng, conn, acquisition["cohort_sizes"])
    total_change = _kpis(rng, conn, revenue, acquisition, retention)
    _bridge(rng, conn, total_change)
    _initiatives(conn)
    _experiment(rng, conn)
    _pricing(rng, conn)
    _referrals(rng, conn)
    _data_quality(rng, conn, total_change, acquisition, retention)
    _definitions(conn)
    _chart_catalog(conn)


# --------------------------------------------------------------------------
# helpers

def _month_of(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _month_end(month: str) -> date:
    y, m = (int(x) for x in month.split("-"))
    first_next = date(y + (m == 12), m % 12 + 1, 1)
    return first_next - timedelta(days=1)


def _insert(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0])
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])


# --------------------------------------------------------------------------
# tables

def _metadata(conn: sqlite3.Connection, seed: int) -> None:
    meta = {
        "data_source": "mock",
        "data_label": "MOCK DEVELOPMENT DATA - synthetic values, not findings from the assignment",
        "generated_by": "pipeline.providers.mock",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": str(seed),
        "currency": "USD",
        "as_of_date": AS_OF.isoformat(),
        "q2_period": f"{YEAR}-04-01 to {YEAR}-06-30",
        "q3_period": f"{YEAR}-07-01 to {YEAR}-09-30",
        "schema_version": "1",
    }
    _insert(conn, "run_metadata", [{"key": k, "value": v} for k, v in meta.items()])


def _evidence(conn: sqlite3.Connection) -> None:
    note = "MOCK - synthetic placeholder. No analysis of assignment data was performed."
    rows = [
        ("MOCK-REV", "Mock revenue series", "revenue_monthly"),
        ("MOCK-BRIDGE", "Mock bridge drivers", "bridge_item"),
        ("MOCK-EXP", "Mock experiment outcomes", "experiment_arm, experiment_metric"),
        ("MOCK-PRICE", "Mock pricing series", "pricing_monthly, price_point"),
        ("MOCK-REF", "Mock referral funnel", "referral_funnel, initiative_metric"),
        ("MOCK-RET", "Mock retention cohorts", "retention_cohort, acquisition_weekly"),
    ]
    _insert(conn, "evidence", [
        {"evidence_id": eid, "title": title, "detail": note,
         "method": "Seeded random generator (pipeline/providers/mock.py)", "source_tables": src}
        for eid, title, src in rows
    ])


def _revenue(rng: random.Random, conn: sqlite3.Connection) -> dict:
    rows = []
    totals = {m: 0.0 for m in MONTHS}
    customers_end = 0
    for region in REGIONS:
        region_scale = rng.uniform(0.5, 1.4)
        growth = rng.uniform(-0.02, 0.025)
        for plan in PLANS:
            base_customers = (rng.uniform(700, 1100) if plan == "monthly" else rng.uniform(250, 450)) * region_scale
            price = rng.uniform(28, 36) if plan == "monthly" else rng.uniform(22, 30)
            for i, month in enumerate(MONTHS):
                customers = round(base_customers * (1 + growth) ** i * rng.uniform(0.97, 1.03))
                revenue = round(customers * price * rng.uniform(0.97, 1.03), 2)
                totals[month] += revenue
                if month == MONTHS[-1]:
                    customers_end += customers
                rows.append({"month": month, "region": region, "plan": plan,
                             "revenue": revenue, "paying_customers": customers})
    _insert(conn, "revenue_monthly", rows)
    return {
        "q2": sum(totals[m] for m in Q2_MONTHS),
        "q3": sum(totals[m] for m in Q3_MONTHS),
        "customers_end": customers_end,
    }


def _acquisition(rng: random.Random, conn: sqlite3.Connection) -> dict:
    rows = []
    week = date(YEAR, 1, 5)  # first Monday of the mock year
    signups_by_quarter = {"q2": 0, "q3": 0}
    cohort_sizes: dict[tuple[str, str], int] = {}
    base = rng.uniform(380, 460)
    trend = rng.uniform(-0.004, 0.008)
    i = 0
    while week <= AS_OF:
        organic = round(base * (1 + trend * i) * rng.uniform(0.9, 1.1))
        organic_paid = round(organic * rng.uniform(0.08, 0.14))
        referred = round(rng.uniform(40, 120)) if week >= REFERRAL_START else 0
        referred_paid = round(referred * rng.uniform(0.05, 0.15))
        segments = {
            "organic": (organic, organic_paid),
            "referred": (referred, referred_paid),
            "all": (organic + referred, organic_paid + referred_paid),
        }
        for seg, (s, p) in segments.items():
            rows.append({"week_start": week.isoformat(), "segment": seg, "signups": s, "paid_conversions": p})
            key = (_month_of(week), seg)
            cohort_sizes[key] = cohort_sizes.get(key, 0) + s
        month = _month_of(week)
        if month in Q2_MONTHS:
            signups_by_quarter["q2"] += organic + referred
        elif month in Q3_MONTHS:
            signups_by_quarter["q3"] += organic + referred
        week += timedelta(days=7)
        i += 1
    _insert(conn, "acquisition_weekly", rows)
    return {**signups_by_quarter, "cohort_sizes": cohort_sizes}


def _retention(rng: random.Random, conn: sqlite3.Connection, cohort_sizes: dict) -> dict:
    rows = []
    day30: dict[str, list[tuple[float, int]]] = {"q2": [], "q3": []}
    for (month, segment), size in sorted(cohort_sizes.items()):
        if size == 0:
            continue
        level = rng.uniform(0.82, 0.92)
        decay = rng.uniform(0.12, 0.2)
        for day in RETENTION_DAYS:
            mature = _month_end(month) + timedelta(days=day) <= AS_OF
            rate = None
            if mature:
                rate = round(min(1.0, level * day ** -decay * rng.uniform(0.97, 1.03)), 4)
            rows.append({"cohort_month": month, "segment": segment, "day": day,
                         "cohort_size": size, "retained_rate": rate})
            if segment == "all" and day == 30 and rate is not None:
                if month in Q2_MONTHS:
                    day30["q2"].append((rate, size))
                elif month in Q3_MONTHS:
                    day30["q3"].append((rate, size))
    _insert(conn, "retention_cohort", rows)

    def weighted(pairs: list[tuple[float, int]]) -> float | None:
        n = sum(s for _, s in pairs)
        return sum(r * s for r, s in pairs) / n if n else None

    return {
        "q2": weighted(day30["q2"]),
        "q3": weighted(day30["q3"]),
        "q3_mature_cohorts": len(day30["q3"]),
    }


def _kpis(rng, conn, revenue, acquisition, retention) -> float:
    change = round((revenue["q3"] / revenue["q2"] - 1) * 100, 2)
    signup_growth = round((acquisition["q3"] / acquisition["q2"] - 1) * 100, 2)
    rq2, rq3 = retention["q2"], retention["q3"]
    mock = "MOCK value."
    rows = [
        ("revenue_q2", "Q2 revenue", round(revenue["q2"], 2), "currency", "Q2", "independent", mock, "MOCK-REV"),
        ("revenue_q3", "Q3 revenue", round(revenue["q3"], 2), "currency", "Q3", "independent", mock, "MOCK-REV"),
        ("revenue_change_pct", "Revenue change, Q3 vs Q2", change, "pct", "Q3 vs Q2", "independent", mock, "MOCK-REV"),
        ("revenue_change_pct_reported", "Revenue change (dashboard)",
         round(change + rng.uniform(-1.5, 1.5), 2), "pct", "Q3 vs Q2", "reported", mock, None),
        ("signups_q2", "Q2 sign-ups", acquisition["q2"], "count", "Q2", "independent", mock, "MOCK-RET"),
        ("signups_q3", "Q3 sign-ups", acquisition["q3"], "count", "Q3", "independent", mock, "MOCK-RET"),
        ("signup_growth_pct", "Sign-up growth, Q3 vs Q2", signup_growth, "pct", "Q3 vs Q2", "independent", mock, "MOCK-RET"),
        ("signup_growth_pct_reported", "Sign-up growth (dashboard)",
         round(signup_growth + rng.uniform(-3, 3), 2), "pct", "Q3 vs Q2", "reported", mock, None),
        ("retention30_q2_reported", "30-day retention, Q2 (dashboard)",
         round(rq2 + rng.uniform(-0.05, 0.05), 4) if rq2 is not None else None, "rate", "Q2", "reported", mock, None),
        ("retention30_q3_reported", "30-day retention, Q3 (dashboard)",
         round(rq3 + rng.uniform(-0.05, 0.08), 4) if rq3 is not None else None, "rate", "Q3", "reported", mock, None),
        ("retention30_q2_independent", "30-day retention, Q2 (recomputed)",
         round(rq2, 4) if rq2 is not None else None, "rate", "Q2", "independent", mock, "MOCK-RET"),
        ("retention30_q3_independent", "30-day retention, Q3 (recomputed)",
         round(rq3, 4) if rq3 is not None else None, "rate", "Q3", "independent",
         f"MOCK value. Only {retention['q3_mature_cohorts']} of 3 Q3 cohorts are mature at day 30.", "MOCK-RET"),
        ("paying_customers_end", "Paying customers, end of Q3", revenue["customers_end"], "count",
         "Sep", "independent", mock, "MOCK-REV"),
    ]
    _insert(conn, "kpi", [
        dict(zip(("kpi_id", "label", "value", "unit", "period", "basis", "note", "evidence_id"), r)) for r in rows
    ])
    return change


def _bridge(rng: random.Random, conn: sqlite3.Connection, total: float) -> None:
    causes = [
        "Mock · Paying-customer volume",
        "Mock · Price and plan mix",
        "Mock · Churn",
        "Mock · Payment failures and refunds",
    ]
    shares = [rng.uniform(0.15, 0.45) for _ in range(3)] + [-rng.uniform(0.05, 0.2)]
    explained_share = rng.uniform(0.75, 0.9)
    scale = explained_share / sum(shares)
    rows = []
    half_widths = []
    for i, (cause, share) in enumerate(zip(causes, shares), start=1):
        central = round(total * share * scale, 2)
        hw = round(abs(central) * rng.uniform(0.25, 0.6) + 0.05, 2)
        half_widths.append(hw)
        rows.append({"position": i, "cause": cause, "kind": "driver", "central_pp": central,
                     "low_pp": round(central - hw, 2), "high_pp": round(central + hw, 2),
                     "confidence": rng.choice(["high", "medium", "low"]),
                     "method": "MOCK - random allocation for layout testing", "evidence_id": "MOCK-BRIDGE"})
    # The remainder is computed, never chosen, so the bars always reconcile.
    remainder = round(total - sum(r["central_pp"] for r in rows), 2)
    hw = round(sum(half_widths) / 2, 2)
    rows.append({"position": len(rows) + 1, "cause": "Unexplained remainder", "kind": "unexplained",
                 "central_pp": remainder, "low_pp": round(remainder - hw, 2), "high_pp": round(remainder + hw, 2),
                 "confidence": "low", "method": "Total change minus the sum of explained drivers",
                 "evidence_id": "MOCK-BRIDGE"})
    _insert(conn, "bridge_item", rows)


def _initiatives(conn: sqlite3.Connection) -> None:
    pending = "The assignment data has not been analysed yet."
    rationale = ("No verdict is shown in development mode. Figures on this page are mock values "
                 "that only exercise the layout.")
    monitoring = "Monitoring plan will be defined together with the recommendation."
    rows = [
        ("onboarding", "New onboarding flow", "1 Aug (global rollout)",
         "Randomized test in two countries, then launched everywhere (as stated in the brief)"),
        ("pricing", "European price increase", "1 Sep",
         "15% price increase in Europe (as stated in the brief)"),
        ("referral", "Partner referral programme", "1 Aug",
         "Partners paid for each new workspace they bring in (as stated in the brief)"),
    ]
    _insert(conn, "initiative", [
        {"initiative_id": iid, "name": name, "launched": launched, "scope": scope,
         "recommendation": "PENDING", "confidence": None, "headline": pending,
         "rationale": rationale, "monitoring": monitoring}
        for iid, name, launched, scope in rows
    ])


def _experiment(rng: random.Random, conn: sqlite3.Connection) -> None:
    n = {"control": int(rng.gauss(2000, 35)), "treatment": int(rng.gauss(2000, 35))}
    _insert(conn, "experiment_arm", [
        {"arm": arm, "assigned": n[arm], "countries": "Mock country A, Mock country B",
         "start_date": f"{YEAR}-06-01", "end_date": f"{YEAR}-07-15"}
        for arm in ("control", "treatment")
    ])

    p_act = rng.uniform(0.35, 0.45)
    lift = {"control": 0.0, "treatment": rng.uniform(-0.03, 0.06)}
    p_paid_active = rng.uniform(0.18, 0.28)
    p_ret_active = rng.uniform(0.55, 0.7)
    outcomes = {arm: {"activated": 0, "paid": 0, "active30": 0, "paid30": 0, "revenue": []} for arm in n}
    for arm, size in n.items():
        o = outcomes[arm]
        for _ in range(size):
            activated = rng.random() < p_act + lift[arm]
            paid = rng.random() < (p_paid_active if activated else 0.03)
            active30 = rng.random() < (p_ret_active if activated else 0.15)
            paid30 = paid and rng.random() < 0.8
            o["activated"] += activated
            o["paid"] += paid
            o["active30"] += active30
            o["paid30"] += paid30
            o["revenue"].append(round(rng.uniform(25, 40), 2) * (1 + paid30) if paid else 0.0)

    rows = []
    specs = [
        ("activation", "Activation", "activated"),
        ("paid_conversion", "Paid conversion", "paid"),
        ("retention30_activity", "30-day activity retention", "active30"),
        ("retention30_paid", "30-day paid retention", "paid30"),
    ]
    for pos, (mid, label, key) in enumerate(specs, start=1):
        r = stats.diff_in_proportions(outcomes["treatment"][key], n["treatment"],
                                      outcomes["control"][key], n["control"])
        rows.append(_exp_row(mid, pos, label, "rate", r, n))
    r = stats.diff_in_means(outcomes["treatment"]["revenue"], outcomes["control"]["revenue"])
    rows.append(_exp_row("revenue_per_assigned", len(rows) + 1, "Revenue per assigned workspace", "currency", r, n))
    _insert(conn, "experiment_metric", rows)


def _exp_row(mid, pos, label, unit, r, n) -> dict:
    return {"metric_id": mid, "position": pos, "label": label, "unit": unit,
            "control_value": round(r["control"], 6), "treatment_value": round(r["treatment"], 6),
            "effect": round(r["effect"], 6), "ci_low": round(r["ci_low"], 6), "ci_high": round(r["ci_high"], 6),
            "p_value": round(r["p_value"], 6), "control_n": n["control"], "treatment_n": n["treatment"],
            "note": "MOCK - simulated outcomes, intention-to-treat"}


def _pricing(rng: random.Random, conn: sqlite3.Connection) -> None:
    price_rows = []
    for plan in PLANS:
        for region in REGIONS:
            before = round(rng.uniform(28, 36) if plan == "monthly" else rng.uniform(22, 30), 2)
            after = round(before * (1 + rng.uniform(0.1, 0.2)), 2) if region == "Europe" else before
            price_rows.append({"plan": plan, "region": region, "price_before": before,
                               "price_after": after, "effective_date": f"{YEAR}-09-01"})
    _insert(conn, "price_point", price_rows)

    # ARPPU is derived from the mock revenue table so the two pages agree.
    arppu = conn.execute(
        """SELECT month,
                  CASE WHEN region = 'Europe' THEN 'Europe' ELSE 'Comparison' END AS grp,
                  SUM(revenue) * 1.0 / SUM(paying_customers)
           FROM revenue_monthly GROUP BY month, grp ORDER BY month, grp"""
    ).fetchall()
    rows = [{"month": m, "group_name": g, "metric": "arppu", "value": round(v, 2)} for m, g, v in arppu]
    for group in ("Europe", "Comparison"):
        conv, churn, new = rng.uniform(0.09, 0.13), rng.uniform(0.025, 0.045), rng.uniform(250, 600)
        for month in MONTHS:
            rows += [
                {"month": month, "group_name": group, "metric": "paid_conversion",
                 "value": round(conv * rng.uniform(0.92, 1.08), 4)},
                {"month": month, "group_name": group, "metric": "churn",
                 "value": round(churn * rng.uniform(0.88, 1.12), 4)},
                {"month": month, "group_name": group, "metric": "new_paid",
                 "value": round(new * rng.uniform(0.9, 1.1))},
            ]
    _insert(conn, "pricing_monthly", rows)

    def avg(group: str, metric: str, months: list[str]) -> float:
        vals = [r["value"] for r in rows if r["group_name"] == group and r["metric"] == metric and r["month"] in months]
        return sum(vals) / len(vals)

    pre, post = ["2026-07", "2026-08"], ["2026-09"]
    e_pre, e_post = avg("Europe", "arppu", pre), avg("Europe", "arppu", post)
    c_pre, c_post = avg("Comparison", "arppu", pre), avg("Comparison", "arppu", post)
    no_ci = "MOCK. No uncertainty estimate: a single post-change month cannot support one."
    metrics = [
        ("europe_arppu_pre", "Europe ARPPU, Jul-Aug", e_pre, None, None, "currency", "MOCK"),
        ("europe_arppu_post", "Europe ARPPU, Sep", e_post, None, None, "currency", "MOCK"),
        ("comparison_arppu_pre", "Comparison ARPPU, Jul-Aug", c_pre, None, None, "currency", "MOCK"),
        ("comparison_arppu_post", "Comparison ARPPU, Sep", c_post, None, None, "currency", "MOCK"),
        ("did_arppu", "Difference-in-differences, ARPPU", (e_post - e_pre) - (c_post - c_pre), None, None,
         "currency", no_ci),
        ("europe_churn_pre", "Europe churn, Jul-Aug", avg("Europe", "churn", pre), None, None, "rate", "MOCK"),
        ("europe_churn_post", "Europe churn, Sep", avg("Europe", "churn", post), None, None, "rate", "MOCK"),
        ("europe_conversion_pre", "Europe paid conversion, Jul-Aug",
         avg("Europe", "paid_conversion", pre), None, None, "rate", "MOCK"),
        ("europe_conversion_post", "Europe paid conversion, Sep",
         avg("Europe", "paid_conversion", post), None, None, "rate", "MOCK"),
    ]
    _insert(conn, "initiative_metric", [
        {"initiative_id": "pricing", "metric_id": mid, "position": i, "label": label,
         "value": round(v, 4), "low": lo, "high": hi, "unit": unit, "note": note}
        for i, (mid, label, v, lo, hi, unit, note) in enumerate(metrics, start=1)
    ])


def _referrals(rng: random.Random, conn: sqlite3.Connection) -> None:
    records = round(rng.uniform(900, 1400))
    unique = round(records * (1 - rng.uniform(0.02, 0.08)))
    new = round(unique * rng.uniform(0.6, 0.9))
    activated = round(new * rng.uniform(0.4, 0.6))
    paid = round(activated * rng.uniform(0.2, 0.4))
    retained = round(paid * rng.uniform(0.6, 0.85))
    stages = [
        ("Referral records", records, "Rows in the referral log"),
        ("Unique referred workspaces", unique, "After removing duplicate referrals"),
        ("Genuinely new workspaces", new, "Excludes workspaces that existed before the referral"),
        ("Activated", activated, None),
        ("Converted to paid", paid, None),
        ("Still paying after 30 days", retained, "Mature cohorts only"),
    ]
    _insert(conn, "referral_funnel", [
        {"position": i, "stage": s, "count": c, "note": f"MOCK. {note}" if note else "MOCK"}
        for i, (s, c, note) in enumerate(stages, start=1)
    ])

    payout_rate = round(rng.uniform(40, 80), 2)
    owed = unique * payout_rate
    paid_out = owed * rng.uniform(0.3, 0.7)
    revenue = paid * rng.uniform(25, 40) * rng.uniform(1.2, 2.0)
    metrics = [
        ("payout_per_workspace", "Payout per referred workspace", payout_rate, "currency", "MOCK"),
        ("payouts_owed", "Partner payouts owed", owed, "currency", "MOCK. Programme cost, not negative revenue"),
        ("payouts_paid", "Partner payouts actually paid", paid_out, "currency", "MOCK"),
        ("referred_revenue", "Revenue from referred workspaces (Q3)", revenue, "currency", "MOCK"),
        ("cost_per_paid", "Payout cost per paying referred customer", owed / paid if paid else None,
         "currency", "MOCK"),
        ("incremental_customers", "Incremental paying customers", None, "count",
         "Not identifiable from mock data. Requires a comparison group."),
    ]
    _insert(conn, "initiative_metric", [
        {"initiative_id": "referral", "metric_id": mid, "position": i, "label": label,
         "value": round(v, 2) if v is not None else None, "low": None, "high": None, "unit": unit, "note": note}
        for i, (mid, label, v, unit, note) in enumerate(metrics, start=1)
    ])


def _data_quality(rng, conn, total_change, acquisition, retention) -> None:
    arms = dict(conn.execute("SELECT arm, assigned FROM experiment_arm").fetchall())
    srm = stats.srm_two_arm(arms["control"], arms["treatment"])
    checks = [
        ("pay_dup_ids", "payments", "Duplicate payment IDs", "0 duplicates"),
        ("pay_refund_orphans", "payments", "Refunds without a matching charge", "0 orphans"),
        ("pay_retry_double_count", "payments", "Failed-payment retries counted once", "1 success per invoice"),
        ("sub_overlap", "subscriptions", "Overlapping subscriptions per workspace", "0 overlaps"),
        ("join_pay_sub", "joins", "Payments matched to a subscription", "100% matched"),
        ("join_sub_ws", "joins", "Subscriptions matched to a workspace", "100% matched"),
        ("join_fanout", "joins", "Join cardinality (no row multiplication)", "Row count preserved"),
        ("ev_missing_days", "events", "Days with no event file", "0 missing days"),
        ("ev_late", "events", "Late-arriving events after cohort close", "< 0.5% of events"),
        ("ws_dup_ids", "workspaces", "Duplicate workspace IDs", "0 duplicates"),
        ("ws_country_null", "workspaces", "Workspaces with no country", "0 rows"),
        ("ref_preexisting", "referrals", "Referred workspaces that already existed", "0 rows"),
        ("exp_cross_arm", "experiment", "Workspaces assigned to both arms", "0 workspaces"),
    ]
    rows = []
    for cid, cat, label, expected in checks:
        status = rng.choices(["pass", "warn", "fail"], weights=[6, 3, 1.5])[0]
        observed = "matches expectation" if status == "pass" else f"{rng.uniform(0.1, 4):.1f}% of rows affected"
        rows.append({"check_id": cid, "category": cat, "label": label, "status": status,
                     "observed": f"MOCK: {observed}", "expected": expected,
                     "detail": "Synthetic result. The real check runs once the assignment data is connected."})
    rows.append({
        "check_id": "exp_srm", "category": "experiment", "label": "Sample-ratio mismatch (50/50 split)",
        "status": "warn" if srm["p_value"] < 0.01 else "pass",
        "observed": (f"MOCK: control {arms['control']:,}, treatment {arms['treatment']:,}; "
                     f"chi-square {srm['chi2']:.2f}, p = {srm['p_value']:.3f}"),
        "expected": "p >= 0.01",
        "detail": "Chi-square test of assigned counts against an even split (computed on mock counts).",
    })
    _insert(conn, "dq_check", rows)

    kpi = dict(conn.execute("SELECT kpi_id, value FROM kpi").fetchall())
    recon = [
        ("revenue_change", "Revenue change, Q3 vs Q2", "pct",
         kpi["revenue_change_pct_reported"], kpi["revenue_change_pct"], 0.1),
        ("signup_growth", "Sign-up growth, Q3 vs Q2", "pct",
         kpi["signup_growth_pct_reported"], kpi["signup_growth_pct"], 0.5),
        ("retention30_q2", "30-day retention, Q2", "rate",
         kpi["retention30_q2_reported"], kpi["retention30_q2_independent"], 0.005),
        ("retention30_q3", "30-day retention, Q3", "rate",
         kpi["retention30_q3_reported"], kpi["retention30_q3_independent"], 0.005),
    ]
    out = []
    for mid, label, unit, dash, ind, tol in recon:
        if dash is None or ind is None:
            status = "pending"
        else:
            status = "match" if abs(dash - ind) <= tol else "mismatch"
        out.append({"metric_id": mid, "label": label, "unit": unit, "dashboard_value": dash,
                    "independent_value": ind, "status": status,
                    "explanation": "MOCK values. The real reconciliation compares dashboards/ SQL with "
                                   "an independent recomputation from raw files."})
    _insert(conn, "metric_reconciliation", out)


def _definitions(conn: sqlite3.Connection) -> None:
    confirm = "Proposed definition - to be confirmed against dashboards/ SQL and data/README.md."
    rows = [
        ("revenue", "Revenue", "Successful charges minus refunds, dated by payment date, in reporting currency.",
         "payment"),
        ("signups", "Sign-ups", "New workspaces created in the period.", "workspace"),
        ("retention30_activity", "30-day activity retention",
         "Share of a sign-up cohort with product activity 30 days after sign-up. Only mature cohorts count.",
         "workspace cohort"),
        ("retention30_paid", "30-day paid retention",
         "Share of a cohort that is still paying 30 days after first payment.", "workspace cohort"),
        ("activation", "Activation", "Workspace reaches the activation event within its first 7 days.",
         "workspace"),
        ("paid_conversion", "Paid conversion", "Share of sign-ups that make a successful first payment.",
         "workspace"),
        ("arppu", "ARPPU", "Revenue divided by paying customers in the same month.", "month x group"),
        ("churn", "Churn", "Share of paying customers at the start of a month who cancel or lapse in it.",
         "month x group"),
        ("referral_new", "Genuinely new referred workspace",
         "Referred workspace with no earlier workspace or subscription for the same customer.", "workspace"),
    ]
    _insert(conn, "metric_definition", [
        {"metric_id": mid, "name": name, "definition": d, "grain": grain, "caveats": confirm}
        for mid, name, d, grain in rows
    ])


def _chart_catalog(conn: sqlite3.Connection) -> None:
    mock = "Currently shows MOCK data."
    rows = [
        ("overview_revenue_trend", "overview", "Monthly revenue by region",
         "Total revenue per calendar month, one line per region.",
         "Compare line levels and slopes; the shaded band marks Q3.", mock),
        ("bridge_waterfall", "bridge", "Revenue bridge, Q2 to Q3",
         "How each cause moves revenue from Q2 to Q3, in percentage points of Q2 revenue.",
         "Each bar starts where the previous one ended. Whiskers show the low-high range. "
         "The last bar is the total change; the bars add up to it exactly.", mock),
        ("onboarding_effects", "onboarding", "Treatment effect with 95% interval",
         "Treatment minus control for each rate, in percentage points.",
         "A dot right of zero means the new flow did better. If the line crosses zero, the data "
         "cannot rule out no effect.", mock),
        ("onboarding_rates", "onboarding", "Control vs treatment rates",
         "Each outcome rate for both arms of the experiment.",
         "Compare bar pairs; differences and their uncertainty are in the effect chart.", mock),
        ("pricing_arppu", "pricing", "ARPPU: Europe vs comparison regions",
         "Average revenue per paying customer each month.",
         "Compare how the Europe line moves after the price change with the comparison line.", mock),
        ("pricing_conversion", "pricing", "Paid conversion: Europe vs comparison",
         "Share of sign-ups converting to paid each month.", "Look for a change in Europe after 1 Sep.", mock),
        ("pricing_churn", "pricing", "Monthly churn: Europe vs comparison",
         "Share of paying customers lost each month.", "Look for a change in Europe after 1 Sep.", mock),
        ("pricing_price_points", "pricing", "List prices before and after",
         "List price per plan and region before and after the change.", "Bars are paired per region.", mock),
        ("referral_funnel", "referrals", "Referral funnel",
         "How many referred workspaces survive each step, from referral record to still paying.",
         "Each bar is a share of the first stage; step conversion is shown between bars.", mock),
        ("referral_weekly_signups", "referrals", "Weekly sign-ups by source",
         "New workspaces per week, organic and referred.",
         "The referred line starts when referrals first appear in the data; compare it with the organic level.", mock),
        ("acquisition_signups", "retention", "Weekly sign-ups by source",
         "New workspaces per week, organic and referred.", "Referred sign-ups start when the programme launched.",
         mock),
        ("acquisition_conversion", "retention", "Weekly paid conversion rate by source",
         "Paid conversions divided by sign-ups each week.", "Compare the sources' conversion levels.", mock),
        ("retention_cohorts", "retention", "Cohort retention",
         "Share of each monthly sign-up cohort still active N days later.",
         "Read across a row for one cohort over time, down a column to compare cohorts at the same age. "
         "Hatched cells are cohorts too young to measure.", mock),
        ("dq_reconciliation", "data-quality", "Dashboard vs independent figures",
         "Each dashboard metric next to the pipeline's independent recomputation.",
         "Pairs that differ point at a definition or data problem.", mock),
    ]
    _insert(conn, "chart_catalog", [
        dict(zip(("chart_id", "page", "title", "what_it_shows", "how_to_read", "caveats"), r)) for r in rows
    ])
