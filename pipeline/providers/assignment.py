"""Placeholder for the real assignment pipeline.

The assignment brief and raw data are not available yet, so this provider
deliberately refuses to run instead of producing anything that could be
mistaken for a finding.

When the data arrives, this module will:
  1. read the raw files in bounded chunks with pandas (events are ~20M rows),
  2. aggregate them,
  3. write every table in pipeline/schema.sql with data_source = 'assignment'.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

NAME = "assignment"

EXPECTED_FILES = [
    "data/workspaces.parquet",
    "data/events",
    "data/subscriptions.csv",
    "data/payments.csv",
    "data/experiment.csv",
    "data/referrals.csv",
    "data/support_tickets.csv",
]


class AssignmentDataUnavailable(RuntimeError):
    pass


def populate(conn: sqlite3.Connection, options: dict) -> None:
    root = Path(options.get("data_root", "."))
    missing = [f for f in EXPECTED_FILES if not (root / f).exists()]
    if missing:
        raise AssignmentDataUnavailable(
            "Assignment data not found. Missing: " + ", ".join(missing)
            + ". Use --source mock for development."
        )
    raise AssignmentDataUnavailable(
        "Assignment data is present, but the assignment pipeline has not been written yet. "
        "It must be built after the data has been inspected (see README: 'Connecting the real data')."
    )
