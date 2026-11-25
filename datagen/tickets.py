"""Support tickets with free text, generated from what happened to each workspace.

There is deliberately no category column: the brief says tickets come "with their text",
so themes have to be read from the text. Templates below are the only source of wording.
"""

from __future__ import annotations

import datetime as dt

from datagen.config import P
from datagen.simulate import EXTRACT, NOTICE_DATE, Billing, Funnel, Workspace, at, rng_for

WINDOW_START = dt.date(2026, 3, 1)

TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "payment": [
        ("Card declined but card is fine", "Our renewal failed with a decline but the card works everywhere else. Can you retry the charge?"),
        ("Payment failed", "We got an email saying the payment failed. Nothing changed on our side. Please check."),
        ("Billing error on renewal", "The payment page shows an error and the invoice is unpaid. We don't want to lose access."),
        ("Charged twice?", "I see two attempts on my statement for the same invoice. Is something wrong with your payment system?"),
        ("Subscription cancelled after failed payment", "Our account was downgraded because a payment failed. We never got a chance to fix it."),
    ],
    "pricing": [
        ("Price increase", "We received the notice that our price goes up 15%. That's a lot for a team our size. Is there any discount?"),
        ("Why is the price going up?", "Your email says the price increases from October. We've been customers for years, why the change?"),
        ("Considering cancelling", "With the new price we're comparing alternatives. Can you explain what we get for the increase?"),
        ("New pricing in EUR", "The new EUR price is higher than the USD price after conversion. Why do European customers pay more?"),
    ],
    "cancel_price": [
        ("Cancelling - too expensive", "We're cancelling at the end of this period. The price is too high for what we use."),
        ("Please cancel our plan", "Please cancel. Budget is tight and the upcoming increase made the decision for us."),
    ],
    "onboarding": [
        ("How do I invite my team?", "I created a workspace but can't find where to invite colleagues. The setup steps were confusing."),
        ("Stuck in setup", "The setup wizard keeps asking for a project template. I just want to start adding tasks."),
        ("Getting started help", "Is there a guide for getting started? I'm not sure what to do after creating the workspace."),
    ],
    "onboarding_emails": [
        ("Too many emails", "I'm getting a lot of 'finish your setup' emails. How do I turn them off?"),
        ("Unsubscribe from reminders", "Please stop the onboarding reminder emails. I clicked one just to make them stop."),
    ],
    "referral": [
        ("I didn't create this account", "A consultant set this workspace up for us. We never planned to use it. Please close it."),
        ("Unknown workspace", "I got a welcome email for a workspace I don't remember creating. It mentions a partner."),
        ("Partner signed us up", "Our agency created this account during a workshop. We're not going to use it."),
    ],
    "duplicate_account": [
        ("Second workspace by mistake", "I already have a paid workspace. A partner link made me create a new one. Can you merge them?"),
        ("Two accounts", "I seem to have two workspaces now after following a partner's link. Which one is billed?"),
    ],
    "general": [
        ("Bug: tasks not saving", "Sometimes when I edit a task the change doesn't save until I refresh."),
        ("Feature request: Gantt view", "Would love a timeline / Gantt view for projects."),
        ("Export to CSV", "How can I export all tasks to a spreadsheet?"),
        ("Login issue", "My colleague can't log in with Google SSO."),
        ("Slow loading", "The board view has been slow to load this week."),
    ],
}


def tickets_for(ws: Workspace, f: Funnel, b: Billing) -> list[dict]:
    rng = rng_for(5, ws.idx)
    out: list[dict] = []

    def add(theme: str, when: dt.datetime) -> None:
        if not (WINDOW_START <= when.date() < EXTRACT):
            return
        subject, body = TEMPLATES[theme][int(rng.integers(0, len(TEMPLATES[theme])))]
        out.append({"workspace_id": ws.workspace_id, "created_at": when,
                    "channel": ["email", "chat", "web_form"][int(rng.integers(0, 3))], "subject": subject, "body": body})

    for t in b.failed_attempts:
        if rng.random() < 0.15:
            add("payment", t + dt.timedelta(hours=int(rng.integers(1, 48))))
    sub = b.subscription
    if sub and ws.currency in P["price_increase_currencies"]:
        started = sub["started_at"].date()
        ended = sub["ended_at"].date() if sub["ended_at"] else EXTRACT
        if started < NOTICE_DATE < ended and rng.random() < 0.07:
            add("pricing", at(NOTICE_DATE + dt.timedelta(days=int(rng.integers(0, 40))), rng))
    if sub and sub["cancel_reason"] == "too_expensive" and rng.random() < 0.3:
        add("cancel_price", sub["cancelled_at"])
    if ws.origin != "initial" and ws.created_at.date() >= WINDOW_START:
        if not f.activated and rng.random() < (0.03 if f.flow == "v1" else 0.015):
            add("onboarding", ws.created_at + dt.timedelta(days=int(rng.integers(0, 5)), hours=int(rng.integers(1, 20))))
        if f.flow == "v2" and rng.random() < 0.012:
            add("onboarding_emails", ws.created_at + dt.timedelta(days=int(rng.integers(5, 25))))
        if ws.origin == "referral_incremental":
            if rng.random() < 0.05:
                add("referral", ws.created_at + dt.timedelta(days=int(rng.integers(1, 20))))
    if b.paid_from:
        months = max(0.0, ((b.paid_until or dt.datetime.combine(EXTRACT, dt.time())) - max(
            b.paid_from, dt.datetime.combine(WINDOW_START, dt.time()))).days / 30)
        for _ in range(int(rng.poisson(0.01 * months))):
            add("general", at(WINDOW_START + dt.timedelta(days=int(rng.integers(0, (EXTRACT - WINDOW_START).days))), rng))
    return out


def duplicate_owner_tickets(ws: Workspace) -> list[dict]:
    rng = rng_for(6, ws.idx)
    if rng.random() >= 0.1:
        return []
    subject, body = TEMPLATES["duplicate_account"][int(rng.integers(0, 2))]
    when = ws.created_at + dt.timedelta(days=int(rng.integers(1, 15)))
    if when.date() >= EXTRACT:
        return []
    return [{"workspace_id": ws.workspace_id, "created_at": when, "channel": "email", "subject": subject, "body": body}]
