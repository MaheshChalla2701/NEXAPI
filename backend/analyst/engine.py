"""Routes analyst questions: local engine always; external narrative only if enabled.

The local answer is computed first and is the fallback for every failure, so
the analyst works with no network, no key and no external provider.
"""

from __future__ import annotations

import sqlite3

from backend.analyst import external, local_engine
from backend.config import Settings

MODES = ("auto", "local", "external")
MAX_QUESTION_CHARS = 500


def ask(conn: sqlite3.Connection, settings: Settings, question: str, mode: str = "auto") -> dict:
    local = local_engine.answer(conn, question)
    local["mode"] = "local"
    if mode == "local":
        return local
    if not settings.external_ready:
        if mode == "external":
            local["notices"].append("External AI is not configured, so the local engine answered. "
                                    "See README: 'Optional external AI'.")
        return local
    try:
        reply = external.ask(settings, question, local, local_engine.grounding_context(conn))
    except external.ExternalUnavailable as exc:
        local["notices"].append(f"External AI unavailable ({exc}); the local engine answered instead.")
        return local
    return {
        **local,
        "mode": "external",
        "provider": settings.external_provider,
        "model": reply["model"],
        "summary": [p.strip() for p in reply["text"].split("\n") if p.strip()],
        "answered": True,
        "limitations": local["limitations"] + [
            "Wording by an external model. Every number in it was checked against the analysis database."],
    }
