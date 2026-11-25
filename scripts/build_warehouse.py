"""SYNTHETIC SCENARIO - the analytics team's warehouse loader.

Loads the raw files in data/ into a SQLite warehouse that the dashboards in dashboards/ query.
Events are NOT copied row by row: they are read in chunks and aggregated to one row per
workspace per day (workspace_daily_activity), counting every event type.

    python3 -m scripts.build_warehouse [--data data] [--out var/warehouse.sqlite]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV_TABLES = ["subscriptions", "payments", "experiment", "referrals", "support_tickets", "fx_rates"]


def build(data_dir: Path, out: Path, chunksize: int = 200_000) -> dict[str, int]:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    counts: dict[str, int] = {}
    conn = sqlite3.connect(tmp)
    try:
        ws = pd.read_parquet(data_dir / "workspaces.parquet")
        ws["created_at"] = ws["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        ws.to_sql("workspaces", conn, index=False)
        counts["workspaces"] = len(ws)
        for name in CSV_TABLES:
            df = pd.read_csv(data_dir / f"{name}.csv", dtype=str, keep_default_na=False)
            for col in ("amount", "usd_per_unit", "payout_usd", "list_price"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col])
            df.to_sql(name, conn, index=False)
            counts[name] = len(df)

        conn.execute("CREATE TABLE workspace_daily_activity (workspace_id TEXT, activity_date TEXT, n_events INTEGER)")
        n_events = 0
        for path in sorted((data_dir / "events").glob("*.csv.gz")):
            for chunk in pd.read_csv(path, usecols=["workspace_id", "event_ts"], chunksize=chunksize):
                n_events += len(chunk)
                chunk["activity_date"] = chunk["event_ts"].str.slice(0, 10)
                agg = chunk.groupby(["workspace_id", "activity_date"]).size().reset_index(name="n_events")
                agg.to_sql("workspace_daily_activity", conn, index=False, if_exists="append")
        # Late-arriving events can split a workspace-day across two files: merge them.
        conn.executescript("""
            CREATE TABLE wda AS SELECT workspace_id, activity_date, SUM(n_events) AS n_events
                                FROM workspace_daily_activity GROUP BY 1, 2;
            DROP TABLE workspace_daily_activity;
            ALTER TABLE wda RENAME TO workspace_daily_activity;
            CREATE INDEX ix_wda ON workspace_daily_activity (workspace_id, activity_date);
        """)
        counts["events_read"] = n_events
        counts["workspace_daily_activity"] = conn.execute("SELECT COUNT(*) FROM workspace_daily_activity").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp, out)
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--out", type=Path, default=ROOT / "var" / "warehouse.sqlite")
    args = ap.parse_args()
    for k, v in build(args.data, args.out).items():
        print(f"{k:28s} {v:>10,}")


if __name__ == "__main__":
    main()
