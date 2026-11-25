"""Local, rule-based analyst. The default mode; needs no network and no key.

It is NOT a language model. It matches the question to one of a fixed set of
intents, answers from SQLite, and says plainly when a question is outside
what it can answer. Every number in an answer is read from the database.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass, field
from statistics import fmean, pstdev
from typing import Callable

from backend.db import metadata, one, rows


# --------------------------------------------------------------------------
# answer model and formatting

@dataclass
class Answer:
    intent: str
    title: str
    summary: list[str]
    evidence: list[dict] = field(default_factory=list)
    confidence: str = "n/a"
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    answered: bool = True


def fmt(value: float | None, unit: str, currency: str = "USD") -> str:
    if value is None:
        return "not available"
    if unit == "currency":
        return f"{currency} {value:,.0f}" if abs(value) >= 1000 else f"{currency} {value:,.2f}"
    if unit == "currency_diff":
        return ("+" if value >= 0 else "-") + fmt(abs(value), "currency", currency)
    if unit == "rate":
        return f"{value * 100:.1f}%"
    if unit == "rate_diff":
        return f"{value * 100:+.1f} pp"
    if unit == "pct":
        return f"{value:+.1f}%"
    if unit == "pp":
        return f"{value:+.2f} pp"
    if unit == "count":
        return f"{value:,.0f}"
    return str(value)


def ev(label: str, value: str, source: str) -> dict:
    return {"label": label, "value": value, "source": source}


def plain_p(p: float | None) -> str:
    if p is None:
        return "no test available"
    if p < 0.001:
        return "a difference this large would almost never appear by chance if there were no real effect (p < 0.001)"
    return (f"if there were no real effect, a difference at least this large would appear about "
            f"{p * 100:.0f}% of the time by chance (p = {p:.3f})")


class Ctx:
    """Lazy access to the database for one question."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.meta = metadata(conn)
        self.currency = self.meta.get("currency", "USD")
        self.is_mock = self.meta.get("data_source") == "mock"
        self._kpis: dict | None = None

    @property
    def kpis(self) -> dict[str, dict]:
        if self._kpis is None:
            self._kpis = {r["kpi_id"]: r for r in rows(self.conn, "SELECT * FROM kpi")}
        return self._kpis

    def k(self, kpi_id: str) -> str:
        r = self.kpis.get(kpi_id)
        return fmt(r["value"], r["unit"], self.currency) if r else "not available"

    def confidence(self, level: str | None) -> str:
        if self.is_mock:
            return "Not applicable: mock data"
        return level or "not yet assessed"


# --------------------------------------------------------------------------
# intent handlers

def h_summary(c: Ctx, q: str) -> Answer:
    bridge = rows(c.conn, "SELECT cause, central_pp, kind FROM bridge_item ORDER BY ABS(central_pp) DESC")
    top = [b for b in bridge if b["kind"] == "driver"][:2]
    pending = rows(c.conn, "SELECT name FROM initiative WHERE recommendation = 'PENDING'")
    summary = [
        f"Revenue moved {c.k('revenue_change_pct')} from Q2 ({c.k('revenue_q2')}) to Q3 ({c.k('revenue_q3')}).",
        f"Sign-ups changed {c.k('signup_growth_pct')}. Recomputed 30-day retention went from "
        f"{c.k('retention30_q2_independent')} to {c.k('retention30_q3_independent')} "
        f"(dashboard: {c.k('retention30_q2_reported')} to {c.k('retention30_q3_reported')}).",
    ]
    if top:
        summary.append("Largest bridge items: " + "; ".join(
            f"{t['cause']} ({fmt(t['central_pp'], 'pp')})" for t in top) + ".")
    if pending:
        summary.append(f"{len(pending)} of 3 initiative recommendations are still pending analysis.")
    return Answer("summary", "Headline summary", summary,
                  evidence=[ev("Revenue change", c.k("revenue_change_pct"), "kpi.revenue_change_pct"),
                            ev("Sign-up growth", c.k("signup_growth_pct"), "kpi.signup_growth_pct")],
                  confidence=c.confidence(None),
                  limitations=["A summary hides the ranges; open the revenue bridge for uncertainty."],
                  related=["What drove the revenue change?", "How sure are we about each driver?"])


def h_bridge(c: Ctx, q: str) -> Answer:
    items = rows(c.conn, "SELECT * FROM bridge_item ORDER BY position")
    total = c.kpis["revenue_change_pct"]
    drivers = sorted([i for i in items if i["kind"] == "driver"], key=lambda i: -abs(i["central_pp"]))
    rem = next((i for i in items if i["kind"] == "unexplained"), None)
    summary = [f"Revenue changed {fmt(total['value'], 'pct')} from Q2 to Q3. The bridge splits that into "
               f"{len(drivers)} drivers plus an explicit unexplained remainder; the central values add up exactly."]
    for d in drivers:
        summary.append(f"{d['cause']}: {fmt(d['central_pp'], 'pp')} (range {d['low_pp']:+.2f} to "
                       f"{d['high_pp']:+.2f} pp, confidence {c.confidence(d['confidence'])}).")
    if rem:
        summary.append(f"Unexplained remainder: {fmt(rem['central_pp'], 'pp')}.")
    low_conf = [d["cause"] for d in drivers if d["confidence"] == "low"]
    return Answer("bridge", "What drove the revenue change", summary,
                  evidence=[ev(i["cause"], fmt(i["central_pp"], "pp"), f"bridge_item #{i['position']}")
                            for i in items],
                  confidence=c.confidence("mixed; see each driver"),
                  limitations=["Contributions are attributions, not proven causes, unless the method says so.",
                               "Ranges overlap; small drivers may not be distinguishable from zero."],
                  next_actions=[f"Firm up the low-confidence driver: {x}." for x in low_conf][:2],
                  related=["What is in the unexplained remainder?", "Explain the bridge chart"])


def h_unexplained(c: Ctx, q: str) -> Answer:
    rem = one(c.conn, "SELECT * FROM bridge_item WHERE kind = 'unexplained'")
    if not rem:
        return _cannot(c, q, "The bridge has no unexplained remainder row.")
    return Answer("unexplained", "Unexplained remainder", [
        f"The remainder is {fmt(rem['central_pp'], 'pp')} (range {rem['low_pp']:+.2f} to {rem['high_pp']:+.2f} pp).",
        "It is the part of the total change that the identified drivers do not account for. "
        "It is computed as total minus explained drivers, never chosen to make the bridge fit.",
    ], evidence=[ev("Remainder", fmt(rem["central_pp"], "pp"), "bridge_item (kind = unexplained)")],
        confidence=c.confidence(rem["confidence"]),
        limitations=["A large remainder means the drivers found so far are incomplete."],
        next_actions=["Check timing effects (annual renewals, refunds dated in a later quarter).",
                      "Check data-quality failures that could move revenue between periods."],
        related=["What drove the revenue change?", "Which data-quality checks failed?"])


def h_revenue(c: Ctx, q: str) -> Answer:
    rec = one(c.conn, "SELECT * FROM metric_reconciliation WHERE metric_id = 'revenue_change'")
    summary = [f"Q2 revenue: {c.k('revenue_q2')}. Q3 revenue: {c.k('revenue_q3')}. "
               f"Change: {c.k('revenue_change_pct')} (dashboard reports {c.k('revenue_change_pct_reported')})."]
    if rec and rec["status"] == "mismatch":
        summary.append("The dashboard and the independent recomputation disagree; see Data quality.")
    d = one(c.conn, "SELECT definition FROM metric_definition WHERE metric_id = 'revenue'")
    return Answer("revenue", "Q2 vs Q3 revenue", summary,
                  evidence=[ev("Q2 revenue", c.k("revenue_q2"), "kpi.revenue_q2"),
                            ev("Q3 revenue", c.k("revenue_q3"), "kpi.revenue_q3"),
                            ev("Change", c.k("revenue_change_pct"), "kpi.revenue_change_pct")],
                  confidence=c.confidence(None),
                  limitations=[f"Revenue definition used: {d['definition']}" if d else "Definition not recorded."],
                  related=["What drove the revenue change?"])


def h_onboarding(c: Ctx, q: str) -> Answer:
    arms = {a["arm"]: a for a in rows(c.conn, "SELECT * FROM experiment_arm")}
    metrics = rows(c.conn, "SELECT * FROM experiment_metric ORDER BY position")
    srm = one(c.conn, "SELECT * FROM dq_check WHERE check_id = 'exp_srm'")
    init = one(c.conn, "SELECT * FROM initiative WHERE initiative_id = 'onboarding'")
    summary = [f"The test assigned {arms['control']['assigned']:,} workspaces to control and "
               f"{arms['treatment']['assigned']:,} to the new flow ({arms['control']['countries']}; "
               f"{arms['control']['start_date']} to {arms['control']['end_date']}). Effects are intention-to-treat."]
    for m in metrics:
        unit = "rate_diff" if m["unit"] == "rate" else "currency_diff"
        crosses = m["ci_low"] <= 0 <= m["ci_high"]
        summary.append(f"{m['label']}: {fmt(m['control_value'], m['unit'], c.currency)} control vs "
                       f"{fmt(m['treatment_value'], m['unit'], c.currency)} treatment, effect "
                       f"{fmt(m['effect'], unit, c.currency)} (95% interval {fmt(m['ci_low'], unit, c.currency)} to "
                       f"{fmt(m['ci_high'], unit, c.currency)})"
                       + ("; the interval includes zero, so no effect is not ruled out." if crosses else "."))
    if metrics:
        summary.append("In plain words for the first metric: " + plain_p(metrics[0]["p_value"]) + ".")
    summary.append(_recommendation_line(init))
    return Answer("onboarding", "Onboarding experiment", summary,
                  evidence=[ev(m["label"], fmt(m["effect"], "rate_diff" if m["unit"] == "rate" else "currency_diff",
                                                c.currency), f"experiment_metric.{m['metric_id']}") for m in metrics]
                  + ([ev("Sample-ratio check", srm["status"].upper(), "dq_check.exp_srm")] if srm else []),
                  confidence=c.confidence(init["confidence"] if init else None),
                  limitations=["Two countries may not represent the global rollout.",
                               "Statistical significance is not the same as business importance."],
                  next_actions=["Compare post-rollout cohorts in other countries against pre-rollout cohorts."],
                  related=["Should we keep the onboarding flow?", "Explain the onboarding effect chart"])


def h_pricing(c: Ctx, q: str) -> Answer:
    m = {r["metric_id"]: r for r in rows(c.conn, "SELECT * FROM initiative_metric WHERE initiative_id = 'pricing'")}
    pp = rows(c.conn, "SELECT * FROM price_point WHERE price_after != price_before")
    init = one(c.conn, "SELECT * FROM initiative WHERE initiative_id = 'pricing'")

    def v(mid: str) -> str:
        r = m.get(mid)
        return fmt(r["value"], r["unit"], c.currency) if r else "not available"

    summary = []
    if pp:
        avg_change = fmean(p["price_after"] / p["price_before"] - 1 for p in pp) * 100
        summary.append(f"{len(pp)} list prices changed (average {avg_change:+.1f}%), effective {pp[0]['effective_date']}.")
    summary += [
        f"Europe ARPPU: {v('europe_arppu_pre')} before vs {v('europe_arppu_post')} after; comparison regions "
        f"{v('comparison_arppu_pre')} vs {v('comparison_arppu_post')}. Difference-in-differences: {v('did_arppu')}.",
        f"Europe churn {v('europe_churn_pre')} before vs {v('europe_churn_post')} after; paid conversion "
        f"{v('europe_conversion_pre')} vs {v('europe_conversion_post')}.",
        _recommendation_line(init),
    ]
    return Answer("pricing", "European price increase", summary,
                  evidence=[ev(r["label"], fmt(r["value"], r["unit"], c.currency),
                               f"initiative_metric.{k}") for k, r in m.items()],
                  confidence=c.confidence(init["confidence"] if init else None),
                  limitations=[(m.get("did_arppu") or {}).get("note") or "No interval estimate.",
                               "Difference-in-differences assumes Europe would have trended like the comparison group."],
                  next_actions=["Check pre-trends before relying on the comparison.",
                                "Separate new from existing (possibly grandfathered) customers."],
                  related=["Did churn rise in Europe?", "Explain the ARPPU chart"])


def h_referrals(c: Ctx, q: str) -> Answer:
    funnel = rows(c.conn, "SELECT * FROM referral_funnel ORDER BY position")
    m = {r["metric_id"]: r for r in rows(c.conn, "SELECT * FROM initiative_metric WHERE initiative_id = 'referral'")}
    init = one(c.conn, "SELECT * FROM initiative WHERE initiative_id = 'referral'")
    steps = [f"{f['stage']} {f['count']:,}" for f in funnel]
    summary = ["Funnel: " + " -> ".join(steps) + "."]
    if len(funnel) >= 2 and funnel[0]["count"]:
        summary.append(f"{funnel[-1]['count'] / funnel[0]['count'] * 100:.1f}% of referral records end up "
                       "as customers still paying after 30 days.")
    for key in ("payouts_owed", "payouts_paid", "cost_per_paid", "referred_revenue"):
        if key in m:
            summary.append(f"{m[key]['label']}: {fmt(m[key]['value'], m[key]['unit'], c.currency)}.")
    inc = m.get("incremental_customers")
    summary.append("Incrementality: " + (fmt(inc["value"], "count") if inc and inc["value"] is not None
                                         else "not established. A referred customer is not automatically "
                                              "an incremental one."))
    summary.append(_recommendation_line(init))
    return Answer("referrals", "Referral programme", summary,
                  evidence=[ev(f["stage"], f"{f['count']:,}", f"referral_funnel #{f['position']}") for f in funnel],
                  confidence=c.confidence(init["confidence"] if init else None),
                  limitations=["Payouts are a programme cost, reported separately from revenue.",
                               "Without a comparison group, some referred customers may have signed up anyway."],
                  next_actions=["Match referred workspaces against pre-existing customers.",
                                "Compare owed vs paid payouts with finance records."],
                  related=["Should we stop the referral programme?", "Explain the referral funnel"])


def h_retention(c: Ctx, q: str) -> Answer:
    note = c.kpis.get("retention30_q3_independent", {}).get("note") or ""
    d = one(c.conn, "SELECT * FROM metric_definition WHERE metric_id = 'retention30_activity'")
    summary = [
        f"Dashboard 30-day retention: {c.k('retention30_q2_reported')} (Q2) to {c.k('retention30_q3_reported')} (Q3).",
        f"Recomputed: {c.k('retention30_q2_independent')} to {c.k('retention30_q3_independent')}.",
    ]
    if "mature" in note:
        summary.append(note.replace("MOCK value. ", "") + " Young cohorts can make retention look better or worse "
                       "than it will end up.")
    return Answer("retention", "30-day retention", summary,
                  evidence=[ev("Q2 (dashboard)", c.k("retention30_q2_reported"), "kpi.retention30_q2_reported"),
                            ev("Q3 (dashboard)", c.k("retention30_q3_reported"), "kpi.retention30_q3_reported"),
                            ev("Q2 (recomputed)", c.k("retention30_q2_independent"), "kpi.retention30_q2_independent"),
                            ev("Q3 (recomputed)", c.k("retention30_q3_independent"), "kpi.retention30_q3_independent")],
                  confidence=c.confidence(None),
                  limitations=[f"Definition: {d['definition']}" if d else "Definition not recorded.",
                               "Activity retention is not paid retention; it can rise while revenue falls."],
                  next_actions=["Compare retention for the same cohort definition and window in both quarters."],
                  related=["How did sign-ups change?", "Explain the cohort retention chart"])


def h_signups(c: Ctx, q: str) -> Answer:
    q3 = one(c.conn, """SELECT SUM(CASE WHEN segment = 'referred' THEN signups END) AS referred,
                               SUM(CASE WHEN segment = 'all' THEN signups END) AS total
                        FROM acquisition_weekly WHERE week_start BETWEEN ? AND ?""",
             (c.meta["q3_period"][:10], c.meta["q3_period"][-10:]))
    summary = [f"Sign-ups: {c.k('signups_q2')} in Q2 vs {c.k('signups_q3')} in Q3, a change of "
               f"{c.k('signup_growth_pct')} (dashboard: {c.k('signup_growth_pct_reported')})."]
    if q3 and q3["total"]:
        summary.append(f"Referred sign-ups were {(q3['referred'] or 0) / q3['total'] * 100:.1f}% of Q3 sign-ups "
                       "(weeks starting in Q3).")
    return Answer("signups", "Sign-ups", summary,
                  evidence=[ev("Q2 sign-ups", c.k("signups_q2"), "kpi.signups_q2"),
                            ev("Q3 sign-ups", c.k("signups_q3"), "kpi.signups_q3")],
                  confidence=c.confidence(None),
                  limitations=["More sign-ups only add revenue if they convert to paid and stay."],
                  related=["How did 30-day retention change?", "Explain the weekly sign-ups chart"])


def h_data_quality(c: Ctx, q: str) -> Answer:
    checks = rows(c.conn, "SELECT * FROM dq_check ORDER BY status = 'fail' DESC, status = 'warn' DESC, check_id")
    counts = {s: sum(1 for x in checks if x["status"] == s) for s in ("pass", "warn", "fail", "pending")}
    mism = rows(c.conn, "SELECT label FROM metric_reconciliation WHERE status = 'mismatch'")
    bad = [x for x in checks if x["status"] in ("fail", "warn")]
    summary = [f"{len(checks)} checks: {counts['pass']} pass, {counts['warn']} warn, {counts['fail']} fail, "
               f"{counts['pending']} pending."]
    summary += [f"{x['status'].upper()}: {x['label']} ({x['observed']})." for x in bad[:5]]
    if mism:
        summary.append("Dashboard vs recomputed mismatches: " + ", ".join(m["label"] for m in mism) + ".")
    return Answer("data_quality", "Data quality", summary,
                  evidence=[ev(x["label"], x["status"].upper(), f"dq_check.{x['check_id']}") for x in bad[:8]],
                  confidence=c.confidence(None),
                  limitations=["A passing check only covers the specific failure it tests for."],
                  next_actions=[f"Investigate: {x['label']}." for x in bad if x["status"] == "fail"][:3],
                  related=["Why do the dashboard and recomputed figures differ?"])


def h_anomalies(c: Ctx, q: str) -> Answer:
    found = []
    rev = rows(c.conn, "SELECT month, region, SUM(revenue) AS r FROM revenue_monthly GROUP BY month, region "
                       "ORDER BY region, month")
    changes = []
    for prev, cur in zip(rev, rev[1:]):
        if prev["region"] == cur["region"] and prev["r"]:
            changes.append((cur["region"], cur["month"], cur["r"] / prev["r"] - 1))
    found += _zscore_flags(changes, 2.0, lambda x: f"Revenue in {x[0]}, {x[1]}: {x[2] * 100:+.1f}% month on month")
    wk = rows(c.conn, "SELECT week_start, signups FROM acquisition_weekly WHERE segment = 'all' ORDER BY week_start")
    wchanges = [(b["week_start"], b["signups"] / a["signups"] - 1) for a, b in zip(wk, wk[1:]) if a["signups"]]
    found += _zscore_flags(wchanges, 2.5, lambda x: f"Sign-ups, week of {x[0]}: {x[1] * 100:+.1f}% week on week")
    summary = (["These periods moved unusually compared with the rest of their series:"] + found) if found else \
        ["No month-on-month revenue or week-on-week sign-up change stood out (threshold: z-score above 2 / 2.5)."]
    return Answer("anomalies", "Unusual movements", summary,
                  evidence=[ev("Method", "z-score of period-on-period change", "revenue_monthly, acquisition_weekly")],
                  confidence=c.confidence(None),
                  limitations=["A statistical flag shows something moved unusually; it does not say why.",
                               "Short series make z-scores unstable."],
                  next_actions=["Check flagged periods for launches, data gaps or late-arriving records."],
                  related=["Which data-quality checks failed?"])


def _zscore_flags(items: list[tuple], threshold: float, label: Callable[[tuple], str]) -> list[str]:
    vals = [x[-1] for x in items]
    if len(vals) < 4:
        return []
    mu, sd = fmean(vals), pstdev(vals)
    if sd == 0:
        return []
    return [label(x) + f" (z = {(x[-1] - mu) / sd:+.1f})." for x in items if abs((x[-1] - mu) / sd) > threshold]


def h_compare(c: Ctx, q: str) -> Answer:
    inits = rows(c.conn, "SELECT * FROM initiative")
    summary = [f"{i['name']} (launched {i['launched']}): {i['recommendation']}. {i['headline']}" for i in inits]
    return Answer("compare", "The three initiatives side by side", summary,
                  evidence=[ev(i["name"], i["recommendation"], f"initiative.{i['initiative_id']}") for i in inits],
                  confidence=c.confidence(None),
                  limitations=["Initiatives overlap in time (Aug-Sep), so their effects can be confounded."],
                  related=["Tell me about the onboarding experiment", "Tell me about the referral programme"])


INITIATIVE_WORDS = {"onboarding": ("onboarding", "experiment", "flow"),
                    "pricing": ("price", "pricing", "europe"),
                    "referral": ("referral", "partner", "payout")}


def h_recommend(c: Ctx, q: str) -> Answer:
    wanted = [iid for iid, words in INITIATIVE_WORDS.items() if any(w in q for w in words)] or list(INITIATIVE_WORDS)
    inits = [one(c.conn, "SELECT * FROM initiative WHERE initiative_id = ?", (iid,)) for iid in wanted]
    summary, actions = [], []
    for i in inits:
        summary.append(_recommendation_line(i))
        if i["recommendation"] != "PENDING":
            summary.append(f"Why: {i['rationale']}")
            actions += [m for m in i["monitoring"].split("\n") if m.strip()]
    return Answer("recommend", "Recommendations", summary,
                  evidence=[ev(i["name"], i["recommendation"], f"initiative.{i['initiative_id']}") for i in inits],
                  confidence=", ".join(f"{i['name']}: {c.confidence(i['confidence'])}" for i in inits),
                  limitations=["Recommendations are only shown once the analysis supports them; "
                               "the engine never generates one."],
                  next_actions=actions[:4], related=["Compare the three initiatives"])


def h_chart(c: Ctx, q: str) -> Answer:
    charts = rows(c.conn, "SELECT * FROM chart_catalog")
    m = re.search(r"chart:([a-z0-9_]+)", q)
    chart = next((x for x in charts if m and x["chart_id"] == m.group(1)), None)
    if not chart:
        words = set(re.findall(r"[a-z]+", q)) - {"explain", "the", "chart", "graph", "how", "do", "i", "read", "what",
                                                 "does", "show", "this", "a", "plot"}
        scored = sorted(((len(words & set(re.findall(r"[a-z]+", (x["title"] + " " + x["chart_id"]).lower()))), x)
                         for x in charts), key=lambda t: -t[0])
        if scored and scored[0][0] > 0:
            chart = scored[0][1]
    if not chart:
        return Answer("chart", "Which chart?", ["I could not tell which chart you mean. Charts I can explain:"]
                      + [x["title"] for x in charts], answered=False,
                      related=[f"Explain the {x['title'].lower()} chart" for x in charts[:3]])
    return Answer("chart", chart["title"], [chart["what_it_shows"], chart["how_to_read"]],
                  evidence=[ev("Chart", chart["title"], f"chart_catalog.{chart['chart_id']}")],
                  confidence=c.confidence(None), limitations=[chart["caveats"]],
                  related=["What drove the revenue change?"])


def h_definition(c: Ctx, q: str) -> Answer:
    defs = rows(c.conn, "SELECT * FROM metric_definition")
    words = set(re.findall(r"[a-z0-9]+", q))
    scored = sorted(((len(words & set(re.findall(r"[a-z0-9]+", (d["name"] + " " + d["metric_id"]).lower()))), d)
                     for d in defs), key=lambda t: -t[0])
    if not scored or scored[0][0] == 0:
        return Answer("definition", "Metric definitions", ["Metrics with a recorded definition:"]
                      + [d["name"] for d in defs], answered=False)
    d = scored[0][1]
    return Answer("definition", d["name"], [d["definition"], f"Grain: {d['grain']}."],
                  evidence=[ev("Definition", d["name"], f"metric_definition.{d['metric_id']}")],
                  confidence=c.confidence(None), limitations=[d["caveats"]] if d["caveats"] else [])


def h_next_steps(c: Ctx, q: str) -> Answer:
    actions = []
    actions += [f"Resolve failed check: {x['label']}." for x in
                rows(c.conn, "SELECT label FROM dq_check WHERE status = 'fail'")]
    actions += [f"Narrow the range for low-confidence driver: {x['cause']}." for x in
                rows(c.conn, "SELECT cause FROM bridge_item WHERE confidence = 'low' AND kind = 'driver'")]
    actions += [f"Complete the analysis for: {x['name']}." for x in
                rows(c.conn, "SELECT name FROM initiative WHERE recommendation = 'PENDING'")]
    actions += [f"Reconcile: {x['label']}." for x in
                rows(c.conn, "SELECT label FROM metric_reconciliation WHERE status = 'mismatch'")]
    return Answer("next_steps", "What to investigate next",
                  ["Ranked from the open issues recorded in the database:"] + actions[:8],
                  confidence=c.confidence(None),
                  limitations=["This list is built from recorded gaps; it cannot know about gaps nobody has recorded."])


def _recommendation_line(init: dict | None) -> str:
    if not init:
        return "No initiative record found."
    if init["recommendation"] == "PENDING":
        return f"{init['name']}: recommendation pending. {init['headline']}"
    return f"{init['name']}: {init['recommendation']} (confidence {init['confidence']}). {init['headline']}"


def _cannot(c: Ctx, q: str, reason: str | None = None) -> Answer:
    return Answer("unsupported", "Outside what the local engine can answer", [
        reason or "The local analyst only answers questions it can ground in the analysis database, "
                  "and this one does not match any of them.",
        "It will not guess. Try one of the suggested questions, or enable the optional external AI mode "
        "(still grounded in the same data).",
    ], answered=False, related=[s["question"] for s in SUGGESTIONS[:5]])


# --------------------------------------------------------------------------
# intent matching

@dataclass(frozen=True)
class Intent:
    name: str
    handler: Callable[[Ctx, str], Answer]
    anchors: tuple[str, ...]
    terms: tuple[str, ...] = ()


INTENTS = [
    Intent("chart", h_chart, ("chart:", "chart", "graph", "how do i read", "plot")),
    Intent("definition", h_definition, ("define", "definition", "meaning of", "what is meant")),
    Intent("next_steps", h_next_steps, ("next step", "investigate", "what else", "follow up", "to do", "open issue")),
    Intent("recommend", h_recommend, ("recommend", "should we", "keep or", "keep, change", "verdict"),
           ("keep", "stop", "change")),
    Intent("compare", h_compare, ("compare", "all three", "initiatives", "side by side")),
    Intent("unexplained", h_unexplained, ("unexplained", "remainder", "residual")),
    Intent("bridge", h_bridge, ("driver", "drove", "drive", "bridge", "contribut", "waterfall", "cause",
                                "why did revenue", "why is revenue", "why revenue"),
           ("revenue", "decline", "fell", "drop", "pp")),
    Intent("anomalies", h_anomalies, ("anomal", "unusual", "outlier", "spike", "strange")),
    Intent("data_quality", h_data_quality, ("data quality", "duplicate", "missing", "integrity", "discrepanc",
                                            "mismatch", "join"), ("check", "fail", "dashboard")),
    Intent("onboarding", h_onboarding, ("onboarding", "experiment", "treatment", "control group", "a/b"), ("test",)),
    Intent("pricing", h_pricing, ("price", "pricing", "europe", "european", "arppu"), ("churn",)),
    Intent("referrals", h_referrals, ("referral", "partner", "payout", "referred")),
    Intent("retention", h_retention, ("retention", "retained", "cohort")),
    Intent("signups", h_signups, ("sign-up", "signup", "sign up", "acquisition")),
    Intent("revenue", h_revenue, ("revenue change", "q2 revenue", "q3 revenue", "how much revenue", "total revenue"),
           ("revenue", "q2", "q3")),
    Intent("summary", h_summary, ("summary", "summarise", "summarize", "overview", "headline", "what happened")),
]


def match_intent(question: str) -> Intent | None:
    q = question.lower().replace("-", " ")
    best, best_score = None, 0
    for intent in INTENTS:
        score = 3 * sum(a in q for a in intent.anchors) + sum(t in q for t in intent.terms)
        if score > best_score:
            best, best_score = intent, score
    return best if best_score >= 3 else None


SUGGESTIONS = [
    {"question": "What drove the revenue change?", "intent": "bridge"},
    {"question": "Give me the headline summary", "intent": "summary"},
    {"question": "What is in the unexplained remainder?", "intent": "unexplained"},
    {"question": "Tell me about the onboarding experiment", "intent": "onboarding"},
    {"question": "What happened after the European price increase?", "intent": "pricing"},
    {"question": "How is the referral programme performing?", "intent": "referrals"},
    {"question": "How did 30-day retention change?", "intent": "retention"},
    {"question": "Which data-quality checks failed?", "intent": "data_quality"},
    {"question": "Are there any unusual movements in the data?", "intent": "anomalies"},
    {"question": "Compare the three initiatives", "intent": "compare"},
    {"question": "What should we investigate next?", "intent": "next_steps"},
    {"question": "How is 30-day retention defined?", "intent": "definition"},
]


def answer(conn: sqlite3.Connection, question: str) -> dict:
    c = Ctx(conn)
    intent = match_intent(question)
    result = intent.handler(c, question.lower()) if intent else _cannot(c, question)
    out = asdict(result)
    out["data_source"] = c.meta.get("data_source")
    out["notices"] = (["These figures are MOCK development data, not findings from the assignment."]
                      if c.is_mock else [])
    return out


def grounding_context(conn: sqlite3.Connection) -> dict:
    """Compact, verified facts handed to the optional external model."""
    return {
        "run_metadata": metadata(conn),
        "kpis": rows(conn, "SELECT kpi_id, label, value, unit, basis, note FROM kpi"),
        "bridge": rows(conn, "SELECT cause, kind, central_pp, low_pp, high_pp, confidence FROM bridge_item"),
        "initiatives": rows(conn, "SELECT initiative_id, name, recommendation, confidence, headline FROM initiative"),
        "experiment": rows(conn, "SELECT label, unit, control_value, treatment_value, effect, ci_low, ci_high, "
                                 "p_value, control_n, treatment_n FROM experiment_metric"),
        "initiative_metrics": rows(conn, "SELECT initiative_id, label, value, unit, note FROM initiative_metric"),
        "referral_funnel": rows(conn, "SELECT stage, count FROM referral_funnel ORDER BY position"),
        "data_quality": rows(conn, "SELECT label, status, observed FROM dq_check WHERE status != 'pass'"),
    }
