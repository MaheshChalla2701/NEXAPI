"""Integrity checks run on every database build.

A build that fails any check is discarded, so the app never serves a
database whose numbers do not reconcile.
"""

from __future__ import annotations

import sqlite3

TOLERANCE = 1e-6
REQUIRED_METADATA = ("data_source", "data_label", "currency", "as_of_date", "q2_period", "q3_period")
INITIATIVES = {"onboarding", "pricing", "referral"}


class ValidationError(RuntimeError):
    pass


def run(conn: sqlite3.Connection) -> list[str]:
    """Return a list of passed-check descriptions; raise ValidationError on failure."""
    failures: list[str] = []
    passed: list[str] = []

    def check(ok: bool, description: str, failure: str) -> None:
        (passed if ok else failures).append(description if ok else failure)

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    empty = [t for t in tables if conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0]
    check(not empty, f"all {len(tables)} tables populated", f"empty tables: {', '.join(empty)}")

    meta = dict(conn.execute("SELECT key, value FROM run_metadata"))
    missing = [k for k in REQUIRED_METADATA if not meta.get(k)]
    check(not missing, "run metadata complete", f"missing run_metadata keys: {', '.join(missing)}")
    check(meta.get("data_source") in ("mock", "assignment"), "data_source recognised",
          f"data_source must be 'mock' or 'assignment', got {meta.get('data_source')!r}")

    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    check(not fk, "foreign keys resolve", f"{len(fk)} foreign-key violations")

    # Revenue bridge must reconcile exactly to the total change.
    total_row = conn.execute("SELECT value FROM kpi WHERE kpi_id = 'revenue_change_pct'").fetchone()
    if total_row is None or total_row[0] is None:
        failures.append("kpi 'revenue_change_pct' is missing")
    else:
        total = total_row[0]
        central_sum = conn.execute("SELECT SUM(central_pp) FROM bridge_item").fetchone()[0] or 0.0
        check(abs(round(central_sum, 6) - round(total, 6)) <= TOLERANCE,
              f"bridge reconciles: drivers sum to {central_sum:.2f} pp = total {total:.2f}",
              f"bridge does not reconcile: drivers sum to {central_sum:.4f} pp, total is {total:.4f}")
    n_unexplained = conn.execute("SELECT COUNT(*) FROM bridge_item WHERE kind = 'unexplained'").fetchone()[0]
    check(n_unexplained == 1, "bridge has one explicit unexplained bar",
          f"bridge must have exactly one unexplained bar, found {n_unexplained}")

    ids = {r[0] for r in conn.execute("SELECT initiative_id FROM initiative")}
    check(ids == INITIATIVES, "all three initiatives present", f"initiatives found: {sorted(ids)}")
    if meta.get("data_source") == "mock":
        verdicts = conn.execute("SELECT COUNT(*) FROM initiative WHERE recommendation != 'PENDING'").fetchone()[0]
        check(verdicts == 0, "mock build carries no recommendations",
              "mock data must not carry KEEP/CHANGE/STOP recommendations")

    arms = {r[0] for r in conn.execute("SELECT arm FROM experiment_arm")}
    check(arms == {"control", "treatment"}, "experiment has both arms", f"experiment arms found: {sorted(arms)}")
    bad_ci = conn.execute(
        "SELECT metric_id FROM experiment_metric WHERE NOT (ci_low <= effect AND effect <= ci_high)").fetchall()
    check(not bad_ci, "experiment intervals contain their estimates",
          f"intervals not containing the estimate: {[r[0] for r in bad_ci]}")

    funnel = [r[0] for r in conn.execute("SELECT count FROM referral_funnel ORDER BY position")]
    check(all(a >= b for a, b in zip(funnel, funnel[1:])), "referral funnel never increases",
          f"referral funnel increases between stages: {funnel}")

    bad_rates = conn.execute(
        """SELECT COUNT(*) FROM retention_cohort WHERE retained_rate IS NOT NULL
           AND (retained_rate < 0 OR retained_rate > 1)""").fetchone()[0]
    bad_rates += conn.execute(
        """SELECT COUNT(*) FROM kpi WHERE unit = 'rate' AND value IS NOT NULL
           AND (value < 0 OR value > 1)""").fetchone()[0]
    check(bad_rates == 0, "all rates within 0-1", f"{bad_rates} rate values outside 0-1")

    if failures:
        raise ValidationError("Database validation failed:\n  - " + "\n  - ".join(failures))
    return passed
