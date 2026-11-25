"""Customer-level simulation: workspaces, onboarding funnel, subscriptions and payments.

Every random draw comes from a generator keyed by (seed, stream, workspace index[, path]),
so each workspace's history is reproducible on its own and does not shift when other
workspaces change. That lets the calibration flip one decision (annual vs monthly for the
Q2-2025 promotion cohort) without disturbing anything else.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, field

import numpy as np

from datagen.config import COUNTRIES, P, fx_usd_per_unit

D, DT = dt.date, dt.datetime
DAY = dt.timedelta(days=1)

Q2, Q3 = P["q2"], P["q3"]
EXTRACT = P["extract_date"]
SIM_START = P["sim_start"]
PRICE_DATE = P["price_increase_date"]
EXISTING_PRICE_DATE = D(2026, 10, 1)
NOTICE_DATE = P["price_notice_date"]
PROCESSOR_MIGRATION = D(2026, 7, 1)


def rng_for(*key: int) -> np.random.Generator:
    return np.random.default_rng([P["seed"], *key])


def add_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return D(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def at(d: dt.date, rng: np.random.Generator, lo: int = 0, hi: int = 86399) -> dt.datetime:
    return DT(d.year, d.month, d.day) + dt.timedelta(seconds=int(rng.integers(lo, hi + 1)))


def hexid(rng: np.random.Generator, prefix: str, n: int = 12) -> str:
    return f"{prefix}_{int(rng.integers(0, 2**62)):016x}"[: len(prefix) + 1 + n]


# --------------------------------------------------------------------------------------------
# workspaces

@dataclass
class Workspace:
    idx: int
    workspace_id: str
    created_at: dt.datetime
    country: str
    currency: str
    europe: bool
    size: str
    channel: str
    owner_hash: str
    origin: str  # initial | organic | referral_cannibalised | referral_incremental
    partner_id: str | None = None
    exp_arm: str | None = None
    # initial base only
    initial_start: dt.date | None = None
    initial_interval: str | None = None
    initial_tier: str | None = None


@dataclass
class Partner:
    partner_id: str
    weight: float
    cannibal_prob: float


CHANNELS = (["organic_search", "direct", "paid_ads", "content", "app_marketplace"], [0.34, 0.24, 0.22, 0.12, 0.08])
SIZES = (["1-5", "6-20", "21-50"], [0.55, 0.35, 0.10])


def make_partners() -> list[Partner]:
    rng = rng_for(9)
    n = P["referral_partners"]
    raw = rng.beta(2.4, 5.6, n)  # mean 0.3
    weights = np.array([1 / (i + 1) ** 0.9 for i in range(n)])
    weights /= weights.sum()
    return [Partner(f"pt_{i + 1:03d}", float(weights[i]), float(raw[i])) for i in range(n)]


def generate_workspaces(partners: list[Partner]) -> list[Workspace]:
    rng = rng_for(1)
    codes = [c[0] for c in COUNTRIES]
    cw = np.array([c[1] for c in COUNTRIES])
    cw = cw / cw.sum()
    meta = {c[0]: c for c in COUNTRIES}
    out: list[Workspace] = []

    def new(created: dt.datetime, origin: str, country: str | None = None, partner: str | None = None,
            channel: str | None = None) -> Workspace:
        cc = country or codes[rng.choice(len(codes), p=cw)]
        ws = Workspace(
            idx=len(out), workspace_id=hexid(rng, "ws", 10), created_at=created, country=cc,
            currency=meta[cc][2], europe=meta[cc][3],
            size=SIZES[0][rng.choice(3, p=SIZES[1])],
            channel=channel or CHANNELS[0][rng.choice(len(CHANNELS[0]), p=CHANNELS[1])],
            owner_hash=f"{int(rng.integers(0, 2**62)):016x}", origin=origin, partner_id=partner)
        out.append(ws)
        return ws

    # 1. Paying customers already on the books at sim_start (older workspaces).
    for _ in range(P["initial_paying_customers"]):
        start = SIM_START - dt.timedelta(days=int(rng.integers(100, 1400)))
        ws = new(at(start - dt.timedelta(days=int(rng.integers(7, 40))), rng), "initial")
        ws.initial_start = start
        ws.initial_interval = "annual" if rng.random() < P["annual_share"] else "monthly"
        ws.initial_tier = "team" if rng.random() < (0.6 if ws.size != "1-5" else P["team_share"]) else "starter"

    # 2. Daily sign-ups, organic and referred.
    pw = np.array([p.weight for p in partners])
    cannibal_mean = float(sum(p.weight * p.cannibal_prob for p in partners))
    test_lo, test_hi = P["onboarding_test_window"]
    day = SIM_START
    while day < EXTRACT:
        months = (day.year - 2025) * 12 + day.month - 1
        weekend = P["weekend_factor"] if day.weekday() >= 5 else 1.0
        lam = (P["organic_signups_per_day_start"] * (1 + P["organic_growth_per_month"]) ** months
               * P["signup_seasonality"][day.month] * weekend)
        ref_lam = 0.0
        if day >= P["referral_launch"]:
            ramp = min(1.0, ((day - P["referral_launch"]).days + 1) / 14)
            ref_lam = P["referral_signups_per_day"] * ramp * (0.7 if day.weekday() >= 5 else 1.0)
            lam -= cannibal_mean * ref_lam  # these people now arrive through a partner link instead
        for _ in range(int(rng.poisson(max(lam, 0.0)))):
            ws = new(at(day, rng), "organic")
            if ws.country in P["onboarding_test_countries"] and test_lo <= day <= test_hi:
                ws.exp_arm = "treatment" if rng.random() < 0.5 else "control"
        for _ in range(int(rng.poisson(ref_lam))):
            p = partners[int(rng.choice(len(partners), p=pw))]
            origin = "referral_cannibalised" if rng.random() < p.cannibal_prob else "referral_incremental"
            new(at(day, rng), origin, partner=p.partner_id, channel="partner_referral")
        day += DAY

    # 3. Some incremental referred workspaces belong to owners who already have a workspace.
    initial = [w for w in out if w.origin == "initial"]
    for w in out:
        if w.origin == "referral_incremental" and rng.random() < P["referral_existing_owner_share"]:
            w.owner_hash = initial[int(rng.integers(0, len(initial)))].owner_hash
    return out


# --------------------------------------------------------------------------------------------
# funnel (independent of the calibrated lever)

@dataclass
class Funnel:
    flow: str | None
    activated: bool
    activation_day: int | None
    converted_at: dt.datetime | None
    u_plan: float
    tier: str | None


def funnel(ws: Workspace) -> Funnel:
    rng = rng_for(2, ws.idx)
    u_plan = float(rng.random())
    if ws.origin == "initial":
        return Funnel(None, True, None, None, u_plan, ws.initial_tier)
    created = ws.created_at.date()
    v2 = created >= P["onboarding_global_launch"] or ws.exp_arm == "treatment"
    low = ws.origin == "referral_incremental"
    p_act = P["activation_base"] + P["activation_size_effect"][ws.size] + (P["onboarding_v2_activation_lift"] if v2 else 0)
    if low:
        p_act *= P["referral_low_intent_activation_mult"]
    activated = rng.random() < p_act
    act_day = int(rng.integers(0, 8)) if activated else None
    p_conv = P["conversion_if_activated"] if activated else P["conversion_if_not_activated"]
    if low:
        p_conv *= 0.6
    if ws.europe and created >= PRICE_DATE:
        p_conv *= (1 + P["price_increase_pct"]) ** -P["price_elasticity_new_customers"]
    converts = rng.random() < p_conv
    conv_day = max(int(rng.integers(7, 31)), (act_day or 0) + 1)
    conv_at = ws.created_at + dt.timedelta(days=conv_day, seconds=int(rng.integers(0, 3600)))
    tier = "team" if rng.random() < (0.6 if ws.size != "1-5" else P["team_share"]) else "starter"
    if not converts or conv_at.date() >= EXTRACT:
        conv_at = None
    return Funnel("v2" if v2 else "v1", activated, act_day, conv_at, u_plan, tier if conv_at else None)


def in_promo(f: Funnel) -> bool:
    lo, hi = P["promo_window"]
    return f.converted_at is not None and lo <= f.converted_at.date() <= hi


# --------------------------------------------------------------------------------------------
# billing

def list_price(currency: str, tier: str, interval: str, charge_date: dt.date, sub_start: dt.date) -> float:
    base = P["prices_monthly"][currency][tier] * (10 if interval == "annual" else 1)
    if currency in P["price_increase_currencies"] and (sub_start >= PRICE_DATE or charge_date >= EXISTING_PRICE_DATE):
        base = round(base * (1 + P["price_increase_pct"]), 2)
    return round(base, 2)


VOLUNTARY_REASONS = (["not_using", "too_expensive", "missing_features", "switched_tool", "other"],
                     [0.35, 0.20, 0.20, 0.15, 0.10])
FAIL_CODES = (["card_declined", "insufficient_funds", "expired_card"], [0.5, 0.3, 0.2])


@dataclass
class Billing:
    subscription: dict | None = None
    payments: list[dict] = field(default_factory=list)
    q2_usd: float = 0.0  # dashboard definition: successful charges, duplicates included
    q3_usd: float = 0.0
    paid_from: dt.datetime | None = None
    paid_until: dt.datetime | None = None  # None = still paying at extract
    failed_attempts: list[dt.datetime] = field(default_factory=list)


def _usd(amount: float, currency: str, d: dt.date) -> float:
    return amount * fx_usd_per_unit(currency, d.year, d.month)


def bill(ws: Workspace, f: Funnel, interval: str, path: int) -> Billing:
    rng = rng_for(3, ws.idx, path)
    b = Billing()
    if ws.origin == "initial":
        anchor, tier, tenure_known = ws.initial_start, ws.initial_tier, True
        started = DT(anchor.year, anchor.month, anchor.day) + dt.timedelta(seconds=int(rng.integers(0, 86400)))
    elif f.converted_at is not None:
        anchor, tier, tenure_known = f.converted_at.date(), f.tier, False
        started = f.converted_at
    else:
        return b
    months = 12 if interval == "annual" else 1
    promo = interval == "annual" and in_promo(f) and ws.origin != "initial"
    low = ws.origin == "referral_incremental"
    sub_id = hexid(rng, "sub", 12)
    k = 0
    if tenure_known:  # first period at or after sim_start
        while add_months(anchor, k * months) < SIM_START:
            k += 1
    sub = {"subscription_id": sub_id, "workspace_id": ws.workspace_id, "plan": tier, "billing_interval": interval,
           "currency": ws.currency, "list_price": list_price(ws.currency, tier, interval, anchor, anchor),
           "discount_pct": int(P["promo_discount"] * 100) if promo else 0, "started_at": started,
           "cancelled_at": None, "ended_at": None, "cancel_reason": None, "status": "active"}
    b.paid_from = started
    while True:
        ps = add_months(anchor, k * months)
        if ps >= EXTRACT:
            break
        if k > 0:
            notice = ws.europe and NOTICE_DATE <= ps <= Q3[1]
            if interval == "monthly":
                h = P["monthly_churn_early"] if k <= 3 else P["monthly_churn"]
                h *= (0.7 if ws.size == "21-50" else 1.0) * (0.85 if tier == "team" else 1.0) * (1.7 if low else 1.0)
                mult = P["price_notice_churn_multiplier"] if notice else 1.0
            else:
                h = P["annual_nonrenewal"] * (1.7 if low else 1.0)
                mult = 1.3 if notice else 1.0
            if rng.random() < min(0.95, h * mult):
                price_driven = rng.random() < (mult - 1) / mult
                reason = "too_expensive" if price_driven else VOLUNTARY_REASONS[0][rng.choice(5, p=VOLUNTARY_REASONS[1])]
                cancelled = at(ps - dt.timedelta(days=int(rng.integers(1, 11))), rng)
                sub.update(cancelled_at=cancelled, ended_at=DT(ps.year, ps.month, ps.day), cancel_reason=reason)
                break
        pe = add_months(anchor, (k + 1) * months)
        price = list_price(ws.currency, tier, interval, ps, anchor)
        amount = round(price * (1 - P["promo_discount"]) if promo and k == 0 else price, 2)
        invoice = hexid(rng, "in", 12)
        succeeded = False
        last = None
        for attempt, offset in enumerate((0, 3, 7), start=1):
            d = ps + dt.timedelta(days=offset)
            if d >= EXTRACT:
                break
            ts = at(d, rng)
            last = ts
            if attempt == 1:
                base_fail = P["payment_fail_rate_before"] if d < PROCESSOR_MIGRATION else P["payment_fail_rate_after"]
                fail_p = base_fail
            else:
                fail_p = 1 - P["payment_retry_success"][attempt - 2]
            row = {"payment_id": hexid(rng, "py", 14), "invoice_id": invoice, "subscription_id": sub_id,
                   "workspace_id": ws.workspace_id, "type": "charge", "status": "succeeded", "attempt": attempt,
                   "amount": amount, "currency": ws.currency, "created_at": ts, "period_start": ps,
                   "period_end": pe, "failure_code": None, "refund_of": None}
            if rng.random() < fail_p:
                if d >= PROCESSOR_MIGRATION and attempt == 1 and rng.random() < 1 - P["payment_fail_rate_before"] / base_fail:
                    code = "processor_timeout"
                else:
                    code = FAIL_CODES[0][rng.choice(3, p=FAIL_CODES[1])]
                row.update(status="failed", failure_code=code)
                b.payments.append(row)
                b.failed_attempts.append(ts)
                continue
            b.payments.append(row)
            copies = 2 if rng.random() < P["dq_duplicate_payment_rows"] else 1
            if copies == 2:
                b.payments.append(dict(row))
            usd = _usd(amount, ws.currency, d) * copies
            if Q2[0] <= d <= Q2[1]:
                b.q2_usd += usd
            elif Q3[0] <= d <= Q3[1]:
                b.q3_usd += usd
            succeeded = True
            refund_p = P["refund_rate_first_annual"] if (interval == "annual" and k == 0) else (
                P["refund_rate_monthly"] if interval == "monthly" else 0.0)
            if rng.random() < refund_p:
                rd = ts + dt.timedelta(days=int(rng.integers(1, 15)), seconds=int(rng.integers(0, 3600)))
                if rd.date() < EXTRACT:
                    b.payments.append({**row, "payment_id": hexid(rng, "py", 14), "type": "refund", "attempt": 1,
                                       "created_at": rd, "refund_of": row["payment_id"]})
                    if interval == "annual" and k == 0:
                        sub.update(cancelled_at=rd, ended_at=rd, cancel_reason="refund_requested")
            break
        if sub["ended_at"] is not None:
            break
        if not succeeded:
            if last is not None and (ps + dt.timedelta(days=7)) < EXTRACT:
                sub.update(ended_at=last, cancel_reason="payment_failed")
            else:
                sub["status"] = "past_due"
            break
        k += 1

    if sub["ended_at"] is not None:
        sub["status"] = "ended"
        b.paid_until = sub["ended_at"] if isinstance(sub["ended_at"], DT) else None
    b.subscription = sub
    return b
