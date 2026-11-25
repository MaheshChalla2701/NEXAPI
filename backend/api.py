"""Endpoint payloads. Every function reads SQLite and returns plain JSON data.

No business metric is computed in the frontend: the pipeline computes them,
this module only selects and shapes them. Each payload carries `meta` so the
UI can always show where the numbers came from (mock vs assignment).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.db import metadata, one, rows

Query = dict[str, list[str]]


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------
# shared pieces

def meta(conn: sqlite3.Connection) -> dict[str, Any]:
    md = metadata(conn)
    return {
        "data_source": md.get("data_source"),
        "is_mock": md.get("data_source") == "mock",
        "data_label": md.get("data_label"),
        "currency": md.get("currency"),
        "as_of_date": md.get("as_of_date"),
        "q2_period": md.get("q2_period"),
        "q3_period": md.get("q3_period"),
        "generated_at": md.get("generated_at"),
    }


def _kpis(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["kpi_id"]: r for r in rows(conn, "SELECT * FROM kpi")}


def _initiatives(conn: sqlite3.Connection) -> list[dict]:
    out = rows(conn, "SELECT * FROM initiative ORDER BY CASE initiative_id "
                     "WHEN 'onboarding' THEN 1 WHEN 'pricing' THEN 2 ELSE 3 END")
    for r in out:
        r["monitoring"] = [m for m in r["monitoring"].split("\n") if m.strip()]
    return out


def _initiative(conn: sqlite3.Connection, initiative_id: str) -> dict:
    return next(i for i in _initiatives(conn) if i["initiative_id"] == initiative_id)


def _initiative_metrics(conn: sqlite3.Connection, initiative_id: str) -> list[dict]:
    return rows(conn, "SELECT metric_id, label, value, low, high, unit, note FROM initiative_metric "
                      "WHERE initiative_id = ? ORDER BY position", (initiative_id,))


def _bridge_items(conn: sqlite3.Connection) -> list[dict]:
    return rows(conn, """
        SELECT b.position, b.cause, b.kind, b.central_pp, b.low_pp, b.high_pp, b.confidence, b.method,
               b.evidence_id, e.title AS evidence_title, e.detail AS evidence_detail
        FROM bridge_item b LEFT JOIN evidence e USING (evidence_id)
        ORDER BY b.position""")


def _charts(conn: sqlite3.Connection, page: str) -> dict[str, dict]:
    return {r["chart_id"]: r for r in rows(conn, "SELECT * FROM chart_catalog WHERE page = ?", (page,))}


def _one_of(query: Query, name: str, allowed: list[str], default: str) -> str:
    values = query.get(name)
    if not values:
        return default
    value = values[0]
    if value not in allowed:
        raise ApiError(400, f"Invalid {name!r}: {value!r}. Allowed: {', '.join(allowed)}")
    return value


def _pivot(records: list[dict], key: str, column: str, value: str) -> list[dict]:
    out: dict[str, dict] = {}
    for r in records:
        out.setdefault(r[key], {key: r[key]})[r[column]] = r[value]
    return list(out.values())


# --------------------------------------------------------------------------
# endpoints

def overview(conn: sqlite3.Connection, query: Query) -> dict:
    kpis = _kpis(conn)
    dq = rows(conn, "SELECT status, COUNT(*) AS n FROM dq_check GROUP BY status")
    mismatches = rows(conn, "SELECT label FROM metric_reconciliation WHERE status = 'mismatch'")
    caveats = []
    if meta(conn)["is_mock"]:
        caveats.append("All figures are mock development data. No assignment finding is shown.")
    for k in ("retention30_q3_independent",):
        note = (kpis.get(k) or {}).get("note")
        if note and "mature" in note:
            caveats.append(note.replace("MOCK value. ", ""))
    if mismatches:
        caveats.append("Dashboard and independent figures disagree for: "
                       + ", ".join(m["label"] for m in mismatches) + ".")
    failing = sum(d["n"] for d in dq if d["status"] == "fail")
    if failing:
        caveats.append(f"{failing} data-quality checks failed. See Data quality.")
    trend = rows(conn, """SELECT month, region, SUM(revenue) AS revenue FROM revenue_monthly
                          GROUP BY month, region ORDER BY month, region""")
    return {
        "kpis": kpis,
        "bridge": _bridge_items(conn),
        "initiatives": _initiatives(conn),
        "caveats": caveats,
        "revenue_trend": {"regions": sorted({r["region"] for r in trend}),
                          "rows": _pivot(trend, "month", "region", "revenue")},
        "charts": _charts(conn, "overview"),
    }


def bridge(conn: sqlite3.Connection, query: Query) -> dict:
    items = _bridge_items(conn)
    total = _kpis(conn)["revenue_change_pct"]
    central_sum = round(sum(i["central_pp"] for i in items), 6)
    return {
        "items": items,
        "total": total,
        "reconciliation": {"sum_central_pp": central_sum, "total_pp": total["value"],
                           "difference_pp": round(central_sum - (total["value"] or 0.0), 6)},
        "evidence": rows(conn, "SELECT * FROM evidence WHERE evidence_id IN "
                               "(SELECT evidence_id FROM bridge_item) ORDER BY evidence_id"),
        "charts": _charts(conn, "bridge"),
    }


def onboarding(conn: sqlite3.Connection, query: Query) -> dict:
    return {
        "initiative": _initiative(conn, "onboarding"),
        "arms": rows(conn, "SELECT * FROM experiment_arm ORDER BY arm"),
        "metrics": rows(conn, "SELECT * FROM experiment_metric ORDER BY position"),
        "checks": rows(conn, "SELECT * FROM dq_check WHERE category = 'experiment' ORDER BY check_id"),
        "charts": _charts(conn, "onboarding"),
    }


def pricing(conn: sqlite3.Connection, query: Query) -> dict:
    series = {}
    for metric in ("arppu", "paid_conversion", "churn", "new_paid"):
        recs = rows(conn, "SELECT month, group_name, value FROM pricing_monthly WHERE metric = ? ORDER BY month",
                    (metric,))
        series[metric] = _pivot(recs, "month", "group_name", "value")
    return {
        "initiative": _initiative(conn, "pricing"),
        "price_points": rows(conn, "SELECT * FROM price_point ORDER BY plan, region"),
        "groups": [r["group_name"] for r in rows(conn, "SELECT DISTINCT group_name FROM pricing_monthly "
                                                       "ORDER BY group_name = 'Comparison', group_name")],
        "series": series,
        "metrics": _initiative_metrics(conn, "pricing"),
        "change_month": (one(conn, "SELECT MIN(effective_date) AS d FROM price_point "
                                   "WHERE price_after != price_before") or {}).get("d"),
        "charts": _charts(conn, "pricing"),
    }


def referrals(conn: sqlite3.Connection, query: Query) -> dict:
    weekly = rows(conn, """SELECT week_start, segment, signups, paid_conversions FROM acquisition_weekly
                           WHERE segment IN ('organic', 'referred') ORDER BY week_start""")
    return {
        "initiative": _initiative(conn, "referral"),
        "funnel": rows(conn, "SELECT position, stage, count, note FROM referral_funnel ORDER BY position"),
        "metrics": _initiative_metrics(conn, "referral"),
        "weekly_signups": _pivot(weekly, "week_start", "segment", "signups"),
        "charts": _charts(conn, "referrals"),
    }


def _segments(conn: sqlite3.Connection) -> list[str]:
    segs = [r["segment"] for r in rows(conn, "SELECT DISTINCT segment FROM retention_cohort")]
    return sorted(segs, key=lambda s: (s != "all", s))


def retention(conn: sqlite3.Connection, query: Query) -> dict:
    segments = _segments(conn)
    segment = _one_of(query, "segment", segments, "all")
    recs = rows(conn, """SELECT cohort_month, day, cohort_size, retained_rate FROM retention_cohort
                         WHERE segment = ? ORDER BY cohort_month, day""", (segment,))
    days = sorted({r["day"] for r in recs})
    cohorts: dict[str, dict] = {}
    for r in recs:
        c = cohorts.setdefault(r["cohort_month"], {"cohort_month": r["cohort_month"],
                                                   "cohort_size": r["cohort_size"], "rates": {}})
        c["rates"][str(r["day"])] = r["retained_rate"]

    weekly = rows(conn, "SELECT * FROM acquisition_weekly ORDER BY week_start")
    by_week: dict[str, dict] = {}
    for r in weekly:
        w = by_week.setdefault(r["week_start"], {"week_start": r["week_start"]})
        w[f"{r['segment']}_signups"] = r["signups"]
        w[f"{r['segment']}_conversion"] = (r["paid_conversions"] / r["signups"]) if r["signups"] else None
    kpis = _kpis(conn)
    return {
        "segment": segment,
        "segments": segments,
        "days": days,
        "cohorts": list(cohorts.values()),
        "acquisition": list(by_week.values()),
        "kpis": {k: v for k, v in kpis.items() if k.startswith(("retention30", "signup"))},
        "definitions": rows(conn, "SELECT * FROM metric_definition WHERE metric_id IN "
                                  "('retention30_activity', 'retention30_paid', 'signups', 'paid_conversion')"),
        "charts": _charts(conn, "retention"),
    }


def data_quality(conn: sqlite3.Connection, query: Query) -> dict:
    checks = rows(conn, "SELECT * FROM dq_check ORDER BY category, check_id")
    summary = {s: 0 for s in ("pass", "warn", "fail", "pending")}
    for c in checks:
        summary[c["status"]] += 1
    recon = rows(conn, "SELECT * FROM metric_reconciliation ORDER BY metric_id")
    for r in recon:
        d, i = r["dashboard_value"], r["independent_value"]
        r["difference"] = None if d is None or i is None else round(i - d, 6)
    return {
        "summary": summary,
        "checks": checks,
        "reconciliation": recon,
        "definitions": rows(conn, "SELECT * FROM metric_definition ORDER BY name"),
        "charts": _charts(conn, "data-quality"),
    }


def filters(conn: sqlite3.Connection, query: Query) -> dict:
    return {
        "segments": _segments(conn),
        "months": [r["month"] for r in rows(conn, "SELECT DISTINCT month FROM revenue_monthly ORDER BY month")],
        "regions": [r["region"] for r in rows(conn, "SELECT DISTINCT region FROM revenue_monthly ORDER BY region")],
        "pricing_groups": [r["g"] for r in rows(conn, "SELECT DISTINCT group_name AS g FROM pricing_monthly")],
    }


ENDPOINTS = {
    "/api/overview": overview,
    "/api/bridge": bridge,
    "/api/onboarding": onboarding,
    "/api/pricing": pricing,
    "/api/referrals": referrals,
    "/api/retention": retention,
    "/api/data-quality": data_quality,
    "/api/filters": filters,
}
