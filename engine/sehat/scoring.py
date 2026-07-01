"""Scoring engine — 6 deterministic sub-scores -> FHS + reason codes.

Determinism principle (CLAUDE.md): the score is 100% rule/stat-based and
auditable. Every sub-score is a weighted average of MONOTONE component ramps, so
"perturb one input worse -> the sub-score and the FHS never improve" holds by
construction (verified by tests/test_monotonicity.py).

Missing-data policy (audit must-fix #7): a missing component is dropped and the
remaining component weights are renormalised — the signal is REWEIGHTED, never
scored 0. A whole sub-score with no available inputs is excluded from the FHS and
the six top-level weights renormalise over what remains. Legally-absent data
(EPFO below the 20-employee threshold) is NEUTRAL, never a penalty.

Each sub-score also emits ReasonHits (canonical code + computed slot values). The
explainability layer renders/rephrases these; nothing here is free text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sehat.config import BAND_CUTOFFS, SUBSCORE_WEIGHTS
from sehat.features import Features
from sehat.reason_codes import Polarity, get as get_reason


# ---------------------------------------------------------------------------
# Monotone scaling helpers. Each returns a 0..100 contribution.
# ---------------------------------------------------------------------------
def ramp_up(x: float, lo: float, hi: float) -> float:
    """0 at x<=lo, 100 at x>=hi, linear between. Non-decreasing in x."""
    if hi <= lo:
        return 100.0 if x >= hi else 0.0
    return float(max(0.0, min(100.0, (x - lo) / (hi - lo) * 100.0)))


def ramp_down(x: float, lo: float, hi: float) -> float:
    """100 at x<=lo, 0 at x>=hi, linear between. Non-increasing in x."""
    if hi <= lo:
        return 0.0 if x >= hi else 100.0
    return float(max(0.0, min(100.0, (hi - x) / (hi - lo) * 100.0)))


@dataclass
class ReasonHit:
    """An instance of a reason code with the slot values the engine computed."""
    code: str
    values: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Guardrail for the grounding contract: every value a ReasonHit carries must
        # be a DECLARED slot on its reason code. If a hit smuggled in an undeclared
        # number, the grounding validator would not know it was authorised and could
        # reject a valid narration (or, worse, miss an unauthorised one). Enforce the
        # subset at construction so a typo surfaces here, not in production.
        declared = set(get_reason(self.code).slots)
        provided = set(self.values)
        extra = provided - declared
        if extra:
            raise ValueError(
                f"ReasonHit({self.code!r}) carries undeclared slot(s) {sorted(extra)}; "
                f"declared slots are {sorted(declared)}. Add them to reason_codes.py."
            )

    @property
    def polarity(self) -> Polarity:
        return get_reason(self.code).polarity


@dataclass
class SubScore:
    name: str
    value: float                      # 0..100 (0 if unavailable; excluded from FHS)
    available: bool
    reasons: list[ReasonHit] = field(default_factory=list)
    reweighted: bool = False          # True if some component was missing


@dataclass
class ScoreResult:
    subscores: dict[str, SubScore]
    fhs: float
    band: str
    reasons: list[ReasonHit]          # flattened, ordered strengths-then-risks
    effective_weights: dict[str, float]   # weights actually used (post-reweight)
    any_reweighted: bool


class _Accumulator:
    """Collects (weight, monotone-value) component pairs and renormalises."""

    def __init__(self) -> None:
        self._pairs: list[tuple[float, float]] = []

    def add(self, weight: float, value: float) -> None:
        self._pairs.append((weight, value))

    def resolve(self) -> Optional[float]:
        total_w = sum(w for w, _ in self._pairs)
        if total_w <= 0:
            return None
        return sum(w * v for w, v in self._pairs) / total_w


# ---------------------------------------------------------------------------
# Sub-score 1: Cash-Flow Health (txns + UPI)
# ---------------------------------------------------------------------------
def score_cash_flow(f: Features) -> SubScore:
    acc = _Accumulator()
    reasons: list[ReasonHit] = []
    missing = False

    if f.inflow_cv is not None:
        acc.add(0.45, ramp_down(f.inflow_cv, 0.12, 0.6))   # low CV good
        if f.inflow_cv <= 0.25:
            reasons.append(ReasonHit("CF_INFLOW_CONSISTENT", {"cv": round(f.inflow_cv, 2)}))
        elif f.inflow_cv >= 0.5:
            reasons.append(ReasonHit("CF_INFLOW_VOLATILE", {"cv": round(f.inflow_cv, 2)}))
    else:
        missing = True

    if f.surplus_ratio is not None:
        acc.add(0.35, ramp_up(f.surplus_ratio, 0.0, 0.30))
        pct = round(f.surplus_ratio * 100, 1)
        if f.surplus_ratio >= 0.15:
            reasons.append(ReasonHit("CF_HEALTHY_SURPLUS", {"surplus_ratio_pct": pct}))
        elif f.surplus_ratio < 0.05:
            reasons.append(ReasonHit("CF_THIN_SURPLUS", {"surplus_ratio_pct": pct}))
    else:
        missing = True

    if f.runway_months is not None:
        acc.add(0.20, ramp_up(f.runway_months, 0.5, 4.0))
        rm = round(f.runway_months, 1)
        if f.runway_months >= 3.0:
            reasons.append(ReasonHit("CF_STRONG_RUNWAY", {"runway_months": rm}))
        elif f.runway_months < 1.0:
            reasons.append(ReasonHit("CF_SHORT_RUNWAY", {"runway_months": rm}))
    else:
        missing = True

    value = acc.resolve()
    return SubScore("cash_flow", value or 0.0, value is not None, reasons, missing and value is not None)


# ---------------------------------------------------------------------------
# Sub-score 2: Revenue Vitality (GST + UPI)
# ---------------------------------------------------------------------------
def score_revenue_vitality(f: Features) -> SubScore:
    acc = _Accumulator()
    reasons: list[ReasonHit] = []
    missing = False

    if f.turnover_slope_pct is not None:
        acc.add(0.55, ramp_up(f.turnover_slope_pct, -30.0, 30.0))
        sp = round(f.turnover_slope_pct, 1)
        if f.turnover_slope_pct >= 5:
            reasons.append(ReasonHit("RV_GROWING_TURNOVER", {"slope_pct": sp}))
        elif f.turnover_slope_pct <= -5:
            reasons.append(ReasonHit("RV_DECLINING_TURNOVER", {"slope_pct": sp}))
    else:
        missing = True

    if f.gst_inflow_alignment is not None:
        # Directional & confound-aware: inflow BELOW declared turnover is normal
        # (cash sales, multi-account). Only reward genuine alignment; do NOT
        # penalise inflow<turnover here (integrity excess is the fraud layer's job).
        align = f.gst_inflow_alignment
        # Score peaks when inflow ~ declared turnover (0.7..1.3), tapering only on
        # the low side; the high side is left flat (handled by fraud layer).
        if align >= 1.0:
            comp = 100.0
        else:
            comp = ramp_up(align, 0.4, 1.0)
        acc.add(0.25, comp)
        if 0.7 <= align <= 1.3:
            reasons.append(ReasonHit("RV_GST_INFLOW_ALIGNED", {"alignment": round(align, 2)}))
    else:
        missing = True

    if f.seasonality is not None:
        # Mild seasonality is fine; extreme swings are a small drag.
        acc.add(0.20, ramp_down(f.seasonality, 1.5, 6.0))
        if f.seasonality >= 2.0:
            reasons.append(ReasonHit("RV_SEASONAL", {"seasonality": round(f.seasonality, 1)}))
    else:
        missing = True

    # Operational proxy (electricity/water/fuel) — SUPPLEMENTARY, presence-gated.
    # Fires ONLY when a meter series is present (the thin-file case). Because the
    # _Accumulator renormalises over the components actually added, an absent proxy
    # (every cohort row + P1-P6) leaves this sub-score mathematically identical — the
    # whole spine-safety invariant. Driven by the recent-vs-baseline break: flat or
    # rising consumption => full marks ("operating at capacity"); a >=40% drop => 0.
    # It is deliberately NOT a model feature (model_features.py), so the learned
    # champion/challenger are untouched. Absence never sets `missing` — the proxy is
    # extra evidence, not an expected component, so the reweighted flag is unaffected.
    if f.has_proxy:
        ptype = f.proxy_type or "electricity"
        break_pct = f.proxy_recent_break_pct
        if break_pct is not None:
            acc.add(0.30, ramp_up(break_pct, -40.0, 0.0))
            if break_pct <= -15.0:
                reasons.append(ReasonHit("RV_PROXY_TREND_BREAK", {
                    "proxy_type": ptype,
                    "drop_pct": round(-break_pct, 1),
                    "window": f.proxy_recent_window_months,
                }))
            elif break_pct >= -8.0:
                reasons.append(ReasonHit("RV_PROXY_STABLE", {"proxy_type": ptype}))
        # Always note that a proxy supplemented a thin file (neutral, informational).
        reasons.append(ReasonHit("DS_PROXY_USED", {"proxy_type": ptype}))

    value = acc.resolve()
    return SubScore("revenue_vitality", value or 0.0, value is not None, reasons,
                    missing and value is not None)


# ---------------------------------------------------------------------------
# Sub-score 3: Banking Discipline (txns)
# ---------------------------------------------------------------------------
def score_banking_discipline(f: Features) -> SubScore:
    acc = _Accumulator()
    reasons: list[ReasonHit] = []
    missing = False

    if f.bounce_rate is not None:
        acc.add(0.50, ramp_down(f.bounce_rate, 0.0, 0.10))
        if f.bounce_count == 0:
            reasons.append(ReasonHit("BD_NO_BOUNCES", {}))
        else:
            reasons.append(ReasonHit("BD_BOUNCES", {
                "bounce_count": f.bounce_count,
                "bounce_rate_pct": round(f.bounce_rate * 100, 1)}))
    else:
        missing = True

    if f.neg_balance_days is not None:
        acc.add(0.30, ramp_down(float(f.neg_balance_days), 0.0, 15.0))
        if f.neg_balance_days > 0:
            reasons.append(ReasonHit("BD_NEG_BALANCE_DAYS", {"neg_balance_days": f.neg_balance_days}))
    else:
        missing = True

    if f.median_balance is not None:
        # Buffer scaled against a typical small-MSME cushion.
        acc.add(0.20, ramp_up(f.median_balance, 0.0, 200_000.0))
        if f.median_balance > 0:
            # Pass the RAW number; the template formats it with separators. Keeping
            # the slot numeric lets the grounding validator match against a clean value.
            reasons.append(ReasonHit("BD_HEALTHY_BUFFER",
                                     {"median_balance": round(f.median_balance, 0)}))
    else:
        missing = True

    value = acc.resolve()
    return SubScore("banking_discipline", value or 0.0, value is not None, reasons,
                    missing and value is not None)


# ---------------------------------------------------------------------------
# Sub-score 4: Compliance & Formalization (GST + EPFO)
# ---------------------------------------------------------------------------
def score_compliance(f: Features) -> SubScore:
    acc = _Accumulator()
    reasons: list[ReasonHit] = []
    missing = False

    if f.filing_ontime_pct is not None:
        acc.add(0.50, ramp_up(f.filing_ontime_pct, 40.0, 100.0))
        op = round(f.filing_ontime_pct, 0)
        if f.filing_ontime_pct >= 80:
            reasons.append(ReasonHit("CO_ONTIME_FILING", {"ontime_pct": int(op)}))
        elif f.filing_ontime_pct < 60:
            reasons.append(ReasonHit("CO_LATE_FILING", {"ontime_pct": int(op)}))
    else:
        missing = True

    # Vintage is always available (entity field).
    acc.add(0.30, ramp_up(float(f.vintage_months), 6.0, 48.0))
    if f.vintage_months >= 36:
        reasons.append(ReasonHit("CO_GOOD_VINTAGE", {"vintage_months": f.vintage_months}))
    elif f.vintage_months < 12:
        reasons.append(ReasonHit("CO_THIN_VINTAGE", {"vintage_months": f.vintage_months}))

    # EPFO: bonus-only. If applicable & active -> a positive component; if NOT
    # applicable (sub-threshold) -> NEUTRAL: add a full-marks component so absence
    # is never a penalty, and surface the neutral reason.
    if f.has_epfo_applicable:
        acc.add(0.20, 100.0 if f.epfo_active else 40.0)
        if f.epfo_active:
            reasons.append(ReasonHit("CO_EPFO_ACTIVE", {"employee_count": f.employee_count}))
    else:
        acc.add(0.20, 100.0)   # neutral: no penalty for legally-absent EPFO
        reasons.append(ReasonHit("CO_EPFO_NEUTRAL", {}))

    value = acc.resolve()
    return SubScore("compliance", value or 0.0, value is not None, reasons,
                    missing and value is not None)


# ---------------------------------------------------------------------------
# Sub-score 5: Leverage & Obligations (AA/Txns)
# ---------------------------------------------------------------------------
def score_leverage(f: Features) -> SubScore:
    acc = _Accumulator()
    reasons: list[ReasonHit] = []
    missing = False

    if not f.has_txns:
        return SubScore("leverage", 0.0, False, reasons, False)

    if f.recurring_obligation_detected and f.dscr_proxy is not None:
        acc.add(0.55, ramp_up(min(f.dscr_proxy, 3.0), 1.0, 2.0))
        d = round(f.dscr_proxy, 2)
        if f.dscr_proxy >= 1.5:
            reasons.append(ReasonHit("LV_HEALTHY_DSCR", {"dscr": d}))
        elif f.dscr_proxy < 1.2:
            reasons.append(ReasonHit("LV_TIGHT_DSCR", {"dscr": d}))

        if f.obligation_ratio is not None:
            acc.add(0.45, ramp_down(f.obligation_ratio, 0.10, 0.50))
            op = round(f.obligation_ratio * 100, 0)
            if f.obligation_ratio <= 0.20:
                reasons.append(ReasonHit("LV_LOW_OBLIGATIONS", {"obligation_ratio_pct": int(op)}))
            elif f.obligation_ratio >= 0.40:
                reasons.append(ReasonHit("LV_HIGH_OBLIGATIONS", {"obligation_ratio_pct": int(op)}))
    else:
        # Zero detected debt = UNVERIFIED, never a free 100. Assign a neutral-cautious
        # mid component and surface the honest reason; bureau/GST loans authoritative.
        acc.add(1.0, 60.0)
        reasons.append(ReasonHit("LV_DEBT_UNVERIFIED", {}))

    value = acc.resolve()
    return SubScore("leverage", value or 0.0, value is not None, reasons,
                    missing and value is not None)


# ---------------------------------------------------------------------------
# Sub-score 6: Digital Footprint (UPI)
# ---------------------------------------------------------------------------
def score_digital_footprint(f: Features) -> SubScore:
    acc = _Accumulator()
    reasons: list[ReasonHit] = []
    missing = False

    if f.txn_velocity is not None:
        acc.add(0.40, ramp_up(f.txn_velocity, 5.0, 40.0))
        tv = round(f.txn_velocity, 0)
        if f.txn_velocity >= 30:
            reasons.append(ReasonHit("DF_HIGH_VELOCITY", {"txn_velocity": int(tv)}))
        elif f.txn_velocity < 10:
            reasons.append(ReasonHit("DF_THIN_FOOTPRINT", {"txn_velocity": int(tv)}))
    else:
        missing = True

    if f.unique_counterparties is not None:
        acc.add(0.30, ramp_up(float(f.unique_counterparties), 5.0, 50.0))
        if f.unique_counterparties >= 30:
            reasons.append(ReasonHit("DF_DIVERSE_COUNTERPARTIES",
                                     {"unique_counterparties": f.unique_counterparties}))
    else:
        missing = True

    if f.top1_payer_share is not None:
        acc.add(0.30, ramp_down(f.top1_payer_share, 0.15, 0.7))
        if f.top1_payer_share >= 0.40:
            reasons.append(ReasonHit("DF_CONCENTRATED_PAYERS",
                                     {"top1_share_pct": int(round(f.top1_payer_share * 100, 0))}))
    else:
        missing = True

    value = acc.resolve()
    return SubScore("digital_footprint", value or 0.0, value is not None, reasons,
                    missing and value is not None)


_SUBSCORERS = {
    "cash_flow": score_cash_flow,
    "revenue_vitality": score_revenue_vitality,
    "banking_discipline": score_banking_discipline,
    "compliance": score_compliance,
    "leverage": score_leverage,
    "digital_footprint": score_digital_footprint,
}


def band_for(fhs: float) -> str:
    for name, cutoff in BAND_CUTOFFS:
        if fhs >= cutoff:
            return name
    return BAND_CUTOFFS[-1][0]


def score(f: Features, weights: dict[str, float] | None = None) -> ScoreResult:
    """Compute all six sub-scores and the aggregate FHS.

    `weights` defaults to the fitted SUBSCORE_WEIGHTS. Unavailable sub-scores are
    excluded and the weights renormalise over what remains.
    """
    weights = weights or SUBSCORE_WEIGHTS
    subs: dict[str, SubScore] = {name: fn(f) for name, fn in _SUBSCORERS.items()}

    available = {n: s for n, s in subs.items() if s.available}
    total_w = sum(weights[n] for n in available)
    effective: dict[str, float] = {}
    if total_w > 0:
        fhs = 0.0
        for n, s in available.items():
            w = weights[n] / total_w
            effective[n] = round(w, 4)
            fhs += w * s.value
    else:
        fhs = 0.0

    # Flatten reasons: strengths first, then risks, then neutral (gate reasons
    # are added by the pipeline, not here).
    order = {Polarity.STRENGTH: 0, Polarity.RISK: 1, Polarity.NEUTRAL: 2, Polarity.GATE: 3}
    flat: list[ReasonHit] = [r for s in subs.values() for r in s.reasons]
    flat.sort(key=lambda r: order.get(r.polarity, 9))

    return ScoreResult(
        subscores=subs,
        fhs=round(fhs, 1),
        band=band_for(fhs),
        reasons=flat,
        effective_weights=effective,
        any_reweighted=any(s.reweighted for s in subs.values()) or len(available) < len(subs),
    )
