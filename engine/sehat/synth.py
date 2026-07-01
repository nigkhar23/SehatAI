"""Synthetic cohort generator — the substrate of the validation spine.

THE CENTRAL IDEA (audit must-fix #2). Each entity gets a hidden `true_propensity`
p in [0,1] (higher == more creditworthy). p drives:
  (a) every observable financial signal, each through its OWN noisy emission, and
  (b) the seeded `defaulted_12m` label, through an INDEPENDENT noise channel.

Because the scoring engine later reconstructs an estimate of p along a *different*
path (deterministic sub-score formulas -> weighted sum) than this generator's
noisy emission, and because the label carries noise the features cannot see, the
resulting AUC is high-but-realistic (~0.80), never a circular 1.0. The noise is
what keeps the validation honest.

We emit RAW canonical data (txn lines, GST returns, UPI months, EPFO, bureau) —
NOT pre-computed features. The feature engine derives features downstream, so the
generator and the scorer never share a formula. Everything is deterministic given
a seed (numpy default_rng) so the cohort, metrics, and personas are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from sehat.schema import (
    BureauRecord,
    CanonicalEPFO,
    CanonicalEntity,
    CanonicalGSTReturn,
    CanonicalRecord,
    CanonicalTxn,
    CanonicalUPIMonth,
    Channel,
    ConsentArtefact,
    FIType,
    FilerCadence,
    GSTReturnType,
    LatentLabel,
    OperationalProxy,
    ProxyPoint,
    ProxyType,
    RegType,
    TxnCategory,
    TxnType,
)

# Reference "today" for the synthetic world (matches the project's currentDate).
# The most recent COMPLETE month is the month before this date.
AS_OF = date(2026, 6, 29)

SECTORS = [
    "manufacturing", "retail_trade", "wholesale_trade", "services",
    "food_processing", "textiles", "logistics", "agri_allied",
]
STATES = ["UP", "MH", "GJ", "TN", "KA", "DL", "RJ", "WB", "PB", "TG"]

# Design-intent weights (CLAUDE.md). The default LABEL is generated from the
# intent-weighted blend of per-domain latent factors, so a logistic fit of the
# six sub-scores RECOVERS this hierarchy instead of overturning it — the credible
# story for the deck ("weights are fit, and the fit confirms the design").
INTENT_WEIGHTS: dict[str, float] = {
    "cash_flow": 0.25,
    "revenue_vitality": 0.20,
    "banking_discipline": 0.20,
    "compliance": 0.15,
    "leverage": 0.12,
    "digital_footprint": 0.08,
}

# Per-domain factor = overall propensity + idiosyncratic deviation. FACTOR_SIGMA
# controls cross-domain correlation: small -> all domains track each other
# (collinear, unstable fit); large -> independent (unrealistic). 0.20 gives
# realistic "mostly-correlated, some firms uneven across domains".
FACTOR_SIGMA = 0.20
# Default-label generation from the intent-weighted factor blend. Tuned so the
# base rate is ~18% and the engine's reconstructed AUC lands at a realistic ~0.78
# (not a circular 1.0): the label carries noise the features cannot observe.
LABEL_INTERCEPT = -1.75
LABEL_SLOPE = 4.4
LABEL_SIGMA = 0.55


def _draw_factors(rng: np.random.Generator, p: float) -> dict[str, float]:
    """Draw six semi-independent per-domain health factors around propensity p."""
    return {d: _clip(p + rng.normal(0, FACTOR_SIGMA), 0.02, 0.98) for d in INTENT_WEIGHTS}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def _clip(x: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, x)))


def _months_back(n: int, as_of: date = AS_OF) -> list[str]:
    """Return the n most recent COMPLETE month tags 'YYYY-MM', oldest first."""
    # Start from the first of the current month, step back one month at a time.
    y, m = as_of.year, as_of.month
    tags: list[str] = []
    for _ in range(n):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        tags.append(f"{y:04d}-{m:02d}")
    return list(reversed(tags))


def _month_first_last(tag: str) -> tuple[date, date]:
    y, m = (int(p) for p in tag.split("-"))
    first = date(y, m, 1)
    nm_y, nm_m = (y + 1, 1) if m == 12 else (y, m + 1)
    last = date(nm_y, nm_m, 1) - timedelta(days=1)
    return first, last


@dataclass
class EntityPlan:
    """Resolved per-entity generation parameters derived from latent propensity.

    Each field is the propensity-driven *target*; the generators add independent
    realistic noise around these. Separating plan from emission keeps the
    propensity->signal mapping auditable and lets personas override targets.
    """
    propensity: float
    base_monthly_revenue: float
    months: int                 # bank/UPI history length
    gst_count: int
    inflow_cv: float            # target coefficient of variation of monthly inflow
    surplus_ratio: float        # operating surplus / inflow
    turnover_growth: float      # fractional change over the window (can be negative)
    bounce_rate: float          # fraction of debits that bounce
    filing_ontime_prob: float   # per-return on-time probability
    obligation_ratio: float     # existing debt service / inflow
    top1_share: float           # largest-counterparty inflow share
    credits_per_month: float    # bank-statement credit-line velocity
    vintage_months: int
    headcount: int
    reg_type: RegType
    sector: str
    state: str
    factors: dict[str, float] = field(default_factory=dict)   # per-domain latent health


def _plan_from_propensity(rng: np.random.Generator, p: float) -> EntityPlan:
    """Map a latent propensity to noisy generation targets (the honest core).

    Each observable signal is driven by its OWN domain factor (cf -> cash_flow,
    etc.), not the shared propensity. The signals then carry an extra layer of
    emission noise on top. Because the default label (computed elsewhere) is the
    intent-weighted blend of these same factors, a logistic fit of the six
    sub-scores recovers the design-intent hierarchy — stably, not collinearly.
    """
    base_rev = float(np.exp(rng.normal(np.log(800_000), 0.7)))   # lognormal, median ~8L
    base_rev = _clip(base_rev, 150_000, 6_000_000)

    months = int(rng.choice([6, 9, 12, 12, 12, 18], p=[0.08, 0.12, 0.3, 0.2, 0.2, 0.1]))
    gst_count = min(months, int(rng.choice([2, 3, 4, 6, 8, 12], p=[0.08, 0.12, 0.2, 0.2, 0.2, 0.2])))

    fac = _draw_factors(rng, p)
    cf, rv, bd = fac["cash_flow"], fac["revenue_vitality"], fac["banking_discipline"]
    co, lv, df = fac["compliance"], fac["leverage"], fac["digital_footprint"]

    return EntityPlan(
        propensity=p,
        base_monthly_revenue=base_rev,
        months=months,
        gst_count=gst_count,
        factors=fac,
        # --- Cash-flow domain ---
        inflow_cv=_clip(0.52 - 0.42 * cf + rng.normal(0, 0.07), 0.04, 1.1),
        surplus_ratio=_clip(0.02 + 0.34 * cf + rng.normal(0, 0.06), -0.15, 0.5),
        # --- Revenue domain ---
        turnover_growth=_clip(-0.15 + 0.44 * rv + rng.normal(0, 0.13), -0.6, 0.9),
        # --- Banking-discipline domain ---
        bounce_rate=_clip(0.13 * (1 - bd) + rng.normal(0, 0.02), 0.0, 0.30),
        # --- Compliance domain ---
        filing_ontime_prob=_clip(0.45 + 0.52 * co + rng.normal(0, 0.10), 0.0, 1.0),
        # --- Leverage domain ---
        obligation_ratio=_clip(0.08 + 0.30 * (1 - lv) + rng.normal(0, 0.08), 0.0, 0.6),
        # --- Digital-footprint domain (thin & gameable: noisier emission) ---
        top1_share=_clip(0.42 - 0.22 * df + rng.normal(0, 0.12), 0.08, 0.85),
        credits_per_month=_clip(16 + 20 * df + rng.normal(0, 9), 4, 60),
        # Vintage correlates loosely with compliance/formality.
        vintage_months=int(_clip(10 + 40 * co + rng.normal(0, 20), 4, 130)),
        headcount=int(_clip(rng.poisson(2 + 14 * co), 0, 60)),
        reg_type=RegType(rng.choice(
            [RegType.PROPRIETORSHIP.value, RegType.PARTNERSHIP.value,
             RegType.PVT_LTD.value, RegType.LLP.value],
            p=[0.6, 0.18, 0.15, 0.07],
        )),
        sector=str(rng.choice(SECTORS)),
        state=str(rng.choice(STATES)),
    )


def _gen_gst(rng, plan: EntityPlan) -> list[CanonicalGSTReturn]:
    tags = _months_back(plan.gst_count)
    cadence = FilerCadence.MONTHLY if rng.random() < 0.7 else FilerCadence.QUARTERLY
    out: list[CanonicalGSTReturn] = []
    n = len(tags)
    for i, tag in enumerate(tags):
        # Monthly turnover with the planned growth trend + noise; GST roughly
        # tracks bank revenue but is reported figure (can differ — that's normal).
        trend = 1.0 + plan.turnover_growth * (i / max(1, n - 1))
        turnover = plan.base_monthly_revenue * trend * float(np.exp(rng.normal(0, 0.12)))
        is_nil = rng.random() < 0.03 * (1 - plan.propensity)
        if is_nil:
            turnover = 0.0
        # Effective tax: weak entities sometimes declare turnover but pay ~no tax.
        tax_rate = 0.05 if rng.random() < (0.85 + 0.1 * plan.propensity) else 0.0005
        tax_paid = 0.0 if is_nil else turnover * tax_rate
        first, last = _month_first_last(tag)
        due = last + timedelta(days=20)
        on_time = rng.random() < plan.filing_ontime_prob
        filed = due - timedelta(days=int(rng.integers(1, 6))) if on_time \
            else due + timedelta(days=int(rng.integers(1, 25)))
        out.append(CanonicalGSTReturn(
            period=tag,
            return_type=GSTReturnType.GSTR3B,
            filer_cadence=cadence,
            turnover=round(turnover, 2),
            tax_paid=round(tax_paid, 2),
            is_nil=is_nil,
            filed_on=filed,
            due_on=due,
        ))
    return out


def _split_shares(rng, n: int, top1: float) -> np.ndarray:
    """Return n inflow shares summing to 1 with the largest ~= top1."""
    n = max(1, n)
    if n == 1:
        return np.array([1.0])
    rest = np.array(rng.dirichlet(np.ones(n - 1)) * (1.0 - top1))
    shares = np.concatenate([[top1], rest])
    return shares / shares.sum()


def _gen_txns_and_upi(
    rng, plan: EntityPlan, inject_round_trip: bool = False
) -> tuple[list[CanonicalTxn], list[CanonicalUPIMonth]]:
    tags = _months_back(plan.months)
    n = len(tags)
    txns: list[CanonicalTxn] = []
    upi_months: list[CanonicalUPIMonth] = []

    # Monthly inflow series with the planned CV and growth trend.
    sigma = float(np.sqrt(np.log(1 + plan.inflow_cv**2)))   # lognormal sigma for target CV
    balance = plan.base_monthly_revenue * 0.35              # opening balance

    # A stable pool of customers; concentration decides how skewed they are.
    n_customers = max(3, int(plan.credits_per_month * 1.5))
    customer_ids = [f"cp_{plan.sector[:3]}_{k:03d}" for k in range(n_customers)]

    emi_payee = f"emi_lender_{int(rng.integers(100, 999))}"
    has_emi = plan.obligation_ratio > 0.06
    emi_amount = plan.base_monthly_revenue * plan.obligation_ratio if has_emi else 0.0

    for i, tag in enumerate(tags):
        first, last = _month_first_last(tag)
        days_in_month = (last - first).days + 1
        trend = 1.0 + plan.turnover_growth * (i / max(1, n - 1))
        inflow_total = plan.base_monthly_revenue * trend * float(np.exp(rng.normal(0, sigma)))
        inflow_total = max(0.0, inflow_total)

        n_credits = max(2, int(rng.poisson(plan.credits_per_month)))
        shares = _split_shares(rng, n_credits, plan.top1_share)
        # Map credits onto a skewed subset of customers (top1 share => one big payer).
        chosen = rng.choice(len(customer_ids), size=n_credits, replace=True)
        credit_lines: list[CanonicalTxn] = []
        for j in range(n_credits):
            amt = round(float(inflow_total * shares[j]), 2)
            if amt <= 0:
                continue
            day = int(rng.integers(1, days_in_month + 1))
            cid = customer_ids[chosen[j]]
            credit_lines.append(CanonicalTxn(
                date=first + timedelta(days=day - 1),
                amount=amt, type=TxnType.CREDIT,
                counterparty_id=cid, counterparty=f"Customer {cid[-3:]}",
                channel=Channel.UPI if rng.random() < 0.6 else Channel.NEFT,
                category=TxnCategory.SALES,
                narration=f"UPI/{cid}/sale",
            ))

        # Outflows: operating purchases sized to leave the planned surplus, plus
        # fixed-ish salary/rent/utility, plus the EMI if obligated.
        operating_out = inflow_total * (1.0 - plan.surplus_ratio) * float(np.exp(rng.normal(0, 0.10)))
        operating_out = max(0.0, operating_out - (emi_amount if has_emi else 0.0))
        debit_lines: list[CanonicalTxn] = []

        n_debits = max(2, int(rng.poisson(plan.credits_per_month * 0.6)))
        d_shares = rng.dirichlet(np.ones(n_debits))
        for j in range(n_debits):
            amt = round(float(operating_out * d_shares[j]), 2)
            if amt <= 0:
                continue
            day = int(rng.integers(1, days_in_month + 1))
            debit_lines.append(CanonicalTxn(
                date=first + timedelta(days=day - 1),
                amount=amt, type=TxnType.DEBIT,
                counterparty_id=f"vendor_{int(rng.integers(1, 40)):03d}",
                counterparty="Supplier",
                channel=Channel.UPI if rng.random() < 0.5 else Channel.NEFT,
                category=TxnCategory.PURCHASE,
                narration="UPI/vendor/purchase",
            ))

        if has_emi:
            # Recurring fixed debit: same payee, ~same amount, monthly, low variance.
            amt = round(emi_amount * float(np.exp(rng.normal(0, 0.02))), 2)
            debit_lines.append(CanonicalTxn(
                date=first + timedelta(days=min(5, days_in_month)),
                amount=amt, type=TxnType.DEBIT,
                counterparty_id=emi_payee, counterparty="Lender EMI",
                channel=Channel.ACH, category=TxnCategory.LOAN_EMI,
                narration=f"ACH/{emi_payee}/EMI",
            ))

        # Bounces: returned payments proportional to the planned bounce rate.
        n_bounces = int(rng.poisson(plan.bounce_rate * max(1, n_debits)))
        for _ in range(n_bounces):
            day = int(rng.integers(1, days_in_month + 1))
            debit_lines.append(CanonicalTxn(
                date=first + timedelta(days=day - 1),
                amount=round(float(rng.uniform(1000, 8000)), 2), type=TxnType.DEBIT,
                counterparty_id="bank_charges", counterparty="Return charges",
                channel=Channel.OTHER, category=TxnCategory.BOUNCE,
                narration="CHQ RETURN/insufficient funds",
            ))

        if inject_round_trip:
            # Wash flow: a large credit and near-equal debit with the SAME party,
            # netting to ~zero — the fraud layer must catch this.
            wash = round(plan.base_monthly_revenue * 0.8, 2)
            rt_party = "cp_roundtrip_001"
            day = int(rng.integers(1, days_in_month + 1))
            credit_lines.append(CanonicalTxn(
                date=first + timedelta(days=day - 1), amount=wash, type=TxnType.CREDIT,
                counterparty_id=rt_party, counterparty="Associate Co",
                channel=Channel.RTGS, category=TxnCategory.SALES,
                narration="RTGS/associate/transfer",
            ))
            debit_lines.append(CanonicalTxn(
                date=first + timedelta(days=min(day + 1, days_in_month)),
                amount=round(wash * 0.98, 2), type=TxnType.DEBIT,
                counterparty_id=rt_party, counterparty="Associate Co",
                channel=Channel.RTGS, category=TxnCategory.OTHER,
                narration="RTGS/associate/return",
            ))

        # Order this month's txns by date, then post to the running balance.
        month_txns = sorted(credit_lines + debit_lines, key=lambda t: t.date)
        for t in month_txns:
            balance += t.signed_amount
            t.balance_after = round(balance, 2)
        txns.extend(month_txns)

        # UPI monthly aggregate consistent with the txn mix.
        upi_in_cnt = int(sum(1 for t in credit_lines if t.channel == Channel.UPI))
        upi_out_cnt = int(sum(1 for t in debit_lines if t.channel == Channel.UPI))
        uniq_payers = max(1, len({t.counterparty_id for t in credit_lines}))
        top1 = max(shares) if len(shares) else 0.0
        top3 = float(np.sort(shares)[-3:].sum()) if len(shares) else 0.0
        upi_months.append(CanonicalUPIMonth(
            period=tag,
            inflow_count=max(upi_in_cnt, int(plan.credits_per_month * 1.5)),  # UPI captures small high-freq too
            inflow_amount=round(inflow_total, 2),
            outflow_count=max(upi_out_cnt, int(plan.credits_per_month)),
            outflow_amount=round(operating_out, 2),
            unique_payers=int(uniq_payers + rng.integers(0, 20)),
            unique_payees=int(rng.integers(5, 30)),
            top1_payer_share=round(_clip(top1, 0, 1), 3),
            top3_payer_share=round(_clip(max(top1, top3), 0, 1), 3),
            peak_day_share=round(_clip(plan.top1_share * 0.4 + rng.uniform(0, 0.1), 0, 1), 3),
        ))

    return txns, upi_months


def _gen_epfo(rng, plan: EntityPlan) -> CanonicalEPFO:
    # EPFO mandatory only at 20+ employees. Below that, absence is NEUTRAL.
    if plan.headcount >= 20:
        active = rng.random() < (0.6 + 0.4 * plan.propensity)
        return CanonicalEPFO(
            available=True, active=active, employee_count=plan.headcount,
            monthly_contribution=round(plan.headcount * rng.uniform(1800, 3200), 2),
            since=_months_back(min(plan.vintage_months, 60))[0],
        )
    # Micro unit: sometimes registers voluntarily, usually not — both NEUTRAL.
    if plan.headcount >= 8 and rng.random() < 0.4:
        return CanonicalEPFO(
            available=True, active=True, employee_count=plan.headcount,
            monthly_contribution=round(plan.headcount * rng.uniform(1800, 2600), 2),
            since=_months_back(min(plan.vintage_months, 36))[0],
        )
    return CanonicalEPFO(available=False)


def _gen_operational_proxy(
    rng, months: int, *, proxy_type: ProxyType = ProxyType.ELECTRICITY,
    base_load: float = 4200.0, trend: float = 0.0, noise: float = 0.05,
    unit: str = "kWh",
) -> OperationalProxy:
    """Emit a realistic monthly meter series (seed-driven, never hand-edited).

    `trend` is the fractional change applied linearly across the window (0.0 = flat
    at capacity; negative = a slowdown). Independent lognormal noise per month keeps
    it realistic. This is RAW emission — the feature engine re-derives trend/break by
    its own formula downstream, so the proxy reason code is an honest read, not an echo.
    """
    tags = _months_back(months)
    n = len(tags)
    series: list[ProxyPoint] = []
    for i, tag in enumerate(tags):
        factor = 1.0 + trend * (i / max(1, n - 1))
        value = base_load * factor * float(np.exp(rng.normal(0, noise)))
        series.append(ProxyPoint(period=tag, value=round(max(0.0, value), 1)))
    return OperationalProxy(type=proxy_type, unit=unit, series=series)


def _gen_bureau(rng, plan: EntityPlan, force: dict | None = None) -> BureauRecord:
    """Proprietor-level bureau. Markers correlate with low propensity but draw
    independently so 'thin-but-delinquent' and 'clean-but-thin' both occur."""
    if force is not None:
        return BureauRecord(**force)
    has_file = rng.random() < (0.55 + 0.25 * plan.propensity)
    cibil = None
    if has_file:
        cibil = int(_clip(rng.normal(680 + 120 * plan.propensity, 45), 300, 900))
    sma = None
    r = rng.random()
    # Delinquency markers: more likely at low propensity, independent draws.
    if r < 0.06 * (1 - plan.propensity):
        sma = int(rng.choice([1, 2]))
    writeoff = rng.random() < 0.04 * (1 - plan.propensity)
    settlement = rng.random() < 0.03 * (1 - plan.propensity)
    willful = rng.random() < 0.01 * (1 - plan.propensity)
    enquiries = int(_clip(rng.poisson(1 + 4 * (1 - plan.propensity)), 0, 15))
    return BureauRecord(
        bureau_file=has_file, cibil=cibil, sma_status=sma,
        recent_writeoff=writeoff, settlement=settlement,
        willful_defaulter=willful, enquiries_6m=enquiries,
    )


def _default_label(rng, plan: EntityPlan) -> LatentLabel:
    """Seed the 12-month default label from the INTENT-WEIGHTED blend of the
    per-domain latent factors, through an independent noise channel.

    creditworthiness = Σ INTENT_WEIGHTS[d] * factor[d]
    default_logit    = LABEL_INTERCEPT + LABEL_SLOPE*(0.5 - creditworthiness) + N(0, σ)

    Generating the label from the same weighted blend the engine targets is what
    makes a logistic fit of the six sub-scores RECOVER the design-intent weights
    (rather than collinearly redistributing them). The label noise (σ) is unseen
    by any feature, so even a perfect feature reconstruction cannot perfectly
    predict default — the AUC stays realistic (~0.78), never circular.
    """
    fac = plan.factors
    creditworthiness = sum(INTENT_WEIGHTS[d] * fac[d] for d in INTENT_WEIGHTS)
    logit = LABEL_INTERCEPT + LABEL_SLOPE * (0.5 - creditworthiness) + rng.normal(0, LABEL_SIGMA)
    prob = _sigmoid(logit)
    defaulted = bool(rng.random() < prob)
    # Report the blended creditworthiness as the recorded "true propensity".
    return LatentLabel(true_propensity=round(creditworthiness, 4), defaulted_12m=defaulted)


def _consent(rng, fi_types: list[FIType]) -> ConsentArtefact:
    return ConsentArtefact(
        consent_id=f"c_{int(rng.integers(0x1000, 0xffff)):04x}",
        consent_start=date(2026, 6, 1),
        consent_expiry=date(2026, 8, 31),
        fi_types=fi_types,
        purpose_code="101", purpose_text="credit assessment",
        fetch_type="PERIODIC", data_life_unit="MONTH", data_life_value=3,
        consent_mode="STORE",
    )


def generate_entity(
    rng: np.random.Generator,
    entity_id: str,
    name: str | None = None,
    propensity: float | None = None,
    plan_overrides: dict | None = None,
    bureau_force: dict | None = None,
    inject_round_trip: bool = False,
    drop_sources: tuple[str, ...] = (),
    with_consent: bool = True,
    operational_proxy: list[OperationalProxy] | None = None,
) -> CanonicalRecord:
    """Generate one fully-populated canonical record (with latent label).

    `plan_overrides` lets personas pin specific targets AFTER propensity-derivation
    (e.g. force a thin vintage on an otherwise-strong entity). `drop_sources`
    simulates partial data. The label is always derived from `propensity` so a
    persona's true risk is internally consistent with its inputs.
    """
    if propensity is None:
        propensity = float(rng.beta(2.2, 2.2))
    plan = _plan_from_propensity(rng, propensity)
    if plan_overrides:
        for k, v in plan_overrides.items():
            setattr(plan, k, v)

    entity = CanonicalEntity(
        id=entity_id,
        name=name or f"MSME {entity_id}",
        sector=plan.sector, state=plan.state, reg_type=plan.reg_type,
        gst_registered=True, udyam_vintage_months=plan.vintage_months,
    )

    gst = _gen_gst(rng, plan)
    txns, upi = _gen_txns_and_upi(rng, plan, inject_round_trip=inject_round_trip)
    epfo = _gen_epfo(rng, plan)
    bureau = _gen_bureau(rng, plan, force=bureau_force)

    if "gst" in drop_sources:
        gst = []
    if "txns" in drop_sources:
        txns = []
    if "upi" in drop_sources:
        upi = []
    if "epfo" in drop_sources:
        epfo = None
    if "bureau" in drop_sources:
        bureau = None

    fi_types = [FIType.DEPOSIT, FIType.GST_RETURNS, FIType.UPI]
    if epfo and epfo.available:
        fi_types.append(FIType.EPFO)
    consent = _consent(rng, fi_types) if with_consent else None

    label = _default_label(rng, plan)

    return CanonicalRecord(
        entity=entity, consent=consent, txns=txns, gst_returns=gst,
        upi=upi, epfo=epfo, bureau=bureau,
        operational_proxy=operational_proxy or [],
        label=label,
    )


def generate_cohort(n: int = 600, seed: int = 42) -> list[CanonicalRecord]:
    """Generate a reproducible labeled cohort of n entities."""
    rng = np.random.default_rng(seed)
    records: list[CanonicalRecord] = []
    for i in range(n):
        # Draw propensity per entity from the same rng for full reproducibility.
        p = float(rng.beta(2.2, 2.2))
        rec = generate_entity(rng, entity_id=f"C{i:04d}", propensity=p)
        records.append(rec)
    return records
