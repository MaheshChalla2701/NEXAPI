"""SYNTHETIC SCENARIO - runs the dashboard queries in dashboards/ against the warehouse.

    python3 -m scripts.run_dashboards [--db var/warehouse.sqlite]
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARDS = ROOT / "dashboards"


def run(db: Path) -> dict[str, list[dict]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return {sql.stem: [dict(r) for r in conn.execute(sql.read_text())] for sql in sorted(DASHBOARDS.glob("*.sql"))}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=ROOT / "var" / "warehouse.sqlite")
    args = ap.parse_args()
    for name, rows in run(args.db).items():
        print(f"\n== {name} ==")
        for r in rows:
            print("  " + "  ".join(f"{k}={v}" for k, v in r.items()))


if __name__ == "__main__":
    main()
