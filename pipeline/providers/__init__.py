"""Data providers fill the app schema (pipeline/schema.sql).

A provider is a module exposing:

    NAME: str
    def populate(conn: sqlite3.Connection, options: dict) -> None

It must write every table in the schema and set run_metadata.data_source.
Swapping the mock provider for the real assignment provider changes nothing
in the backend or frontend.
"""

from importlib import import_module
from types import ModuleType

AVAILABLE = {
    "mock": "pipeline.providers.mock",
    "assignment": "pipeline.providers.assignment",
}


def load(name: str) -> ModuleType:
    if name not in AVAILABLE:
        raise SystemExit(f"Unknown data source {name!r}. Choose one of: {', '.join(AVAILABLE)}")
    return import_module(AVAILABLE[name])
