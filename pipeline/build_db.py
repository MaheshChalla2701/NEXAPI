"""Build the SQLite application database.

    python3 -m pipeline.build_db --source mock          # development data
    python3 -m pipeline.build_db --source assignment    # real data (not implemented yet)

The database is built in a temporary file next to the target, validated, and
only then moved into place, so a failed build never replaces a good database.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from pipeline import providers, validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_DB = ROOT / "var" / "app.db"


def build(source: str, db_path: Path, options: dict) -> list[str]:
    provider = providers.load(source)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    try:
        conn = sqlite3.connect(tmp)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(SCHEMA.read_text(encoding="utf-8"))
            with conn:
                provider.populate(conn, options)
            passed = validate.run(conn)
        finally:
            conn.close()
        os.replace(tmp, db_path)
        return passed
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=sorted(providers.AVAILABLE), default="mock")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"output path (default: {DEFAULT_DB})")
    parser.add_argument("--seed", type=int, help="random seed for the mock provider")
    parser.add_argument("--data-root", type=Path, default=ROOT, help="repository root holding data/")
    args = parser.parse_args(argv)

    options = {"data_root": args.data_root}
    if args.seed is not None:
        options["seed"] = args.seed
    try:
        passed = build(args.source, args.db, options)
    except (validate.ValidationError, RuntimeError) as exc:
        print(f"BUILD FAILED ({args.source}): {exc}", file=sys.stderr)
        return 1

    print(f"Built {args.db} from source '{args.source}'")
    for line in passed:
        print(f"  ok  {line}")
    if args.source == "mock":
        print("NOTE: this database contains MOCK development data, not assignment findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
