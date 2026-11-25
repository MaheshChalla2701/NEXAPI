"""Optional external AI narrative layer (Claude Messages API).

Disabled unless ANALYST_EXTERNAL_ENABLED=true and ANTHROPIC_API_KEY is set.
Uses urllib from the standard library so the optional integration adds no
dependency. The model only rewrites verified facts into prose:

  * it receives the verified database context and the local engine's answer;
  * every number in its reply is checked against that context, and the reply
    is discarded (local answer used instead) if any number cannot be traced.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from backend.config import Settings

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """You are the narrative layer of a revenue analytics application used by business leaders.

You receive verified data from the application's database and the answer its rule-based engine produced.
Answer the user's question in plain, non-technical English, under 180 words.

Rules:
- Use only numbers that appear in the verified data or the local answer. Never estimate, extrapolate or round to a
  number that is not derivable by rounding a provided value. Write numbers out in full (no "K" or "M" suffixes).
- If run_metadata.data_source is "mock", say clearly that the figures are mock development data.
- Treat a recommendation of PENDING as "no recommendation yet". Never invent a recommendation.
- Do not present correlation as causation. Mention uncertainty ranges where they exist.
- If the data cannot answer the question, say so and suggest what data would be needed."""

NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


class ExternalUnavailable(RuntimeError):
    pass


def ask(settings: Settings, question: str, local_answer: dict, context: dict) -> dict:
    if not settings.external_ready:
        raise ExternalUnavailable("not configured")
    body = {
        "model": settings.external_model,
        "max_tokens": 16000,
        "system": SYSTEM_PROMPT,
        "output_config": {"effort": settings.external_effort},
        "fallbacks": "default",
        "messages": [{"role": "user", "content": (
            f"<verified_data>\n{json.dumps(context, default=str)}\n</verified_data>\n"
            f"<local_engine_answer>\n{json.dumps(local_answer, default=str)}\n</local_engine_answer>\n"
            f"<question>\n{question}\n</question>")}],
    }
    request = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": settings.anthropic_api_key or "",
            "anthropic-version": API_VERSION,
            "anthropic-beta": FALLBACK_BETA,
        })
    try:
        with urllib.request.urlopen(request, timeout=settings.external_timeout_s) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise ExternalUnavailable(f"provider returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise ExternalUnavailable("provider unreachable") from None

    stop = payload.get("stop_reason")
    if stop == "refusal":
        raise ExternalUnavailable("the model declined the request")
    if stop == "max_tokens":
        raise ExternalUnavailable("the reply was truncated")
    text = "\n".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text").strip()
    if not text:
        raise ExternalUnavailable("empty reply")

    unverified = unverified_numbers(text, [context, local_answer, question])
    if unverified:
        raise ExternalUnavailable("reply contained numbers not found in the verified data: "
                                  + ", ".join(unverified[:5]))
    return {"text": text, "model": payload.get("model", settings.external_model)}


# --------------------------------------------------------------------------
# numeric grounding guard

def _collect(obj: Any, out: list[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out += [float(obj), float(obj) * 100]
    elif isinstance(obj, str):
        out += [float(m.replace(",", "")) for m in NUMBER.findall(obj)]
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, out)


def unverified_numbers(text: str, sources: list[Any]) -> list[str]:
    """Numbers in `text` that cannot be matched (allowing rounding) to any source value.

    Signs are ignored ("fell 4.8%" matches -4.85): this guard catches invented
    numbers, not wording. Small integers (<= 10) are allowed as ordinary words.
    """
    allowed: list[float] = []
    _collect(sources, allowed)
    allowed_abs = [abs(a) for a in allowed]
    bad = []
    for token in NUMBER.findall(text):
        value = float(token.replace(",", ""))
        if value <= 10 and value.is_integer():
            continue
        decimals = len(token.split(".")[1]) if "." in token else 0
        tolerance = 0.5 * 10 ** -decimals + 1e-9
        if not any(abs(value - a) <= tolerance for a in allowed_abs):
            bad.append(token)
    return bad
