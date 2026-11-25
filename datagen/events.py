"""Product events for workspaces created on/after P['events_from'].

Events are produced as compact numpy arrays (not Python objects) so ~1M rows fit easily
in memory. Behaviour depends on the workspace's simulated outcome: onboarding flow,
activation, paid period and referral origin.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from datagen.config import P
from datagen.simulate import Billing, Funnel, Workspace, rng_for

EVENT_TYPES = ["workspace_created", "onboarding_step_completed", "onboarding_email_clicked", "project_created",
               "member_invited", "login", "task_created", "task_completed", "comment_added", "file_uploaded",
               "partner_sync", "checkout_completed"]
T = {name: i for i, name in enumerate(EVENT_TYPES)}
ACTIVITY = np.array([T["login"], T["task_created"], T["task_completed"], T["comment_added"], T["file_uploaded"]])
ACTIVITY_P = np.array([0.35, 0.25, 0.20, 0.15, 0.05])
EPOCH = dt.datetime(1970, 1, 1)


def ts(d: dt.datetime) -> int:
    return int((d - EPOCH).total_seconds())


def workspace_events(ws: Workspace, f: Funnel, b: Billing) -> dict[str, np.ndarray] | None:
    """Return arrays (ts, type, user, step, flow) for one workspace."""
    if ws.origin == "initial" or ws.created_at.date() < P["events_from"]:
        return None
    rng = rng_for(4, ws.idx)
    t0 = ts(ws.created_at)
    end = ts(dt.datetime.combine(P["extract_date"], dt.time()))
    flow = 2 if f.flow == "v2" else 1
    n_users = 1 if not f.activated else 2 + int(rng.poisson({"1-5": 1.0, "6-20": 3.0, "21-50": 6.0}[ws.size]))
    t, ty, us, st = [t0], [T["workspace_created"]], [0], [0]

    # onboarding steps: v1 has 3, v2 has 5
    cont = (0.9, 0.7, 0.5) if flow == 1 else (0.95, 0.85, 0.75, 0.65, 0.55)
    clock = t0
    for step, p in enumerate(cont, start=1):
        if rng.random() > p:
            break
        clock += int(rng.integers(40, 400))
        t.append(clock); ty.append(T["onboarding_step_completed"]); us.append(0); st.append(step)

    if flow == 2:  # reminder emails; clicks are logged as product events
        for k, day in enumerate(P["onboarding_v2_reminder_emails"], start=1):
            if rng.random() < P["email_click_rate"]:
                t.append(t0 + day * 86400 + int(rng.integers(0, 86400))); ty.append(T["onboarding_email_clicked"])
                us.append(0); st.append(k)

    if f.activated:
        ta = max(clock + 60, t0 + f.activation_day * 86400 + int(rng.integers(0, 80000)))
        t += [ta, ta + int(rng.integers(60, 7200))]
        ty += [T["project_created"], T["member_invited"]]
        us += [0, 0]; st += [0, 0]

    if ws.origin == "referral_incremental" and rng.random() < P["referral_partner_sync_events"]:
        for _ in range(1 + int(rng.poisson(3))):
            t.append(t0 + int(rng.integers(1, 31)) * 86400 + int(rng.integers(0, 86400)))
            ty.append(T["partner_sync"]); us.append(0); st.append(0)

    paid_from = ts(b.paid_from) if b.paid_from else None
    paid_until = ts(b.paid_until) if b.paid_until else end
    if paid_from:
        t.append(paid_from); ty.append(T["checkout_completed"]); us.append(0); st.append(0)

    # daily activity
    horizon = (end - t0) // 86400
    if horizon > 0:
        days = np.arange(1, horizon + 1)
        day_ts = t0 + days * 86400
        paying = (paid_from is not None) & (day_ts >= (paid_from or 0)) & (day_ts < paid_until)
        rates = P["activity_daily_prob"]
        (a_act, tau_act), (a_non, tau_non) = rates["activated"], rates["not_activated"]
        p = np.where(paying, rates["paying"],
                     np.where(f.activated, a_act * np.exp(-days / tau_act), a_non * np.exp(-days / tau_non)))
        active = days[rng.random(horizon) < p]
        if active.size:
            counts = 1 + rng.poisson(2.5, active.size)
            dd = np.repeat(active, counts)
            n = dd.size
            t.extend((t0 + dd * 86400 + rng.integers(0, 86400, n)).tolist())
            ty.extend(rng.choice(ACTIVITY, n, p=ACTIVITY_P).tolist())
            us.extend(rng.integers(0, n_users, n).tolist())
            st.extend([0] * n)

    arr_t = np.array(t, dtype=np.int64)
    keep = arr_t < end
    return {
        "ts": arr_t[keep],
        "type": np.array(ty, dtype=np.int8)[keep],
        "user": np.array(us, dtype=np.int16)[keep],
        "step": np.array(st, dtype=np.int8)[keep],
        "flow": np.full(int(keep.sum()), flow, dtype=np.int8),
        "ws": np.full(int(keep.sum()), ws.idx, dtype=np.int32),
    }
