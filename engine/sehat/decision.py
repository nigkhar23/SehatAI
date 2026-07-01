"""Decision layer — turns FHS + gate verdicts into a credit decision + limit.

Decision precedence (deterministic):
  1. Any hard DECLINE gate (consent/bureau/fraud-veto) -> decline, limit 0.
  2. Else any REFER gate (sufficiency/enquiry-velocity/fraud-soft) -> refer.
  3. Else band policy: AA/A -> approve, B -> refer, C/D -> decline.

Indicative limit sizing (audit must-fix #4):
  * Base on trailing MEDIAN net monthly surplus (inflows - operating outflows -
    existing debt service - drawings allowance for proprietorships).
  * Size the EMI so POST-loan DSCR stays >= TARGET (1.3-1.5): the new EMI plus
    observed debt service must be covered by surplus at the target ratio.
  * Apply a volatility haircut from the inflow CV, and a concentration haircut if
    one payer dominates. Floor the DSCR denominator; cap reported DSCR.
  * Zero detected debt is UNVERIFIED, not a free pass — the surplus already nets
    only what we can see, and the limit is conservative by construction.

The output is labelled INDICATIVE — a binding sanction is the bank's act, subject
to KYC / credit policy / KFS. Nothing here is a promise to lend.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sehat.config import (
    ASSUMED_ANNUAL_RATE,
    BAND_DECISION,
    CONCENTRATION_HAIRCUT,
    CONCENTRATION_TOP1_THRESHOLD,
    CONCENTRATION_TOP3_THRESHOLD,
    DEFAULT_TENOR_MONTHS,
    DSCR_CAP,
    MAX_VOLATILITY_HAIRCUT,
    PROPRIETOR_DRAWINGS_FRACTION,
    TARGET_POST_LOAN_DSCR_MAX,
    TARGET_POST_LOAN_DSCR_MIN,
    VOLATILITY_HAIRCUT_K,
)
from sehat.features import Features
from sehat.pipeline import GateStatus, PipelineOutcome
from sehat.schema import CanonicalRecord, RegType
from sehat.scoring import ScoreResult


class Decision(str, Enum):
    APPROVE = "approve"
    REFER = "refer"
    DECLINE = "decline"


@dataclass
class LoanSizing:
    indicative_limit: float
    post_loan_dscr: float
    monthly_surplus_used: float
    volatility_haircut: float
    concentration_haircut: float
    notes: list[str]


@dataclass
class DecisionResult:
    decision: Decision
    band: str
    fhs: float
    sizing: Optional[LoanSizing]
    rationale: str            # which rule fired (machine-stamped, not free narrative)
    blocking_gate: Optional[str]


def _emi(principal: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 12.0
    if r == 0:
        return principal / months
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def _max_principal_for_emi(emi_budget: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 12.0
    if emi_budget <= 0:
        return 0.0
    if r == 0:
        return emi_budget * months
    return emi_budget * ((1 + r) ** months - 1) / (r * (1 + r) ** months)


def size_loan(rec: CanonicalRecord, f: Features) -> LoanSizing:
    """Compute the indicative limit. Conservative by construction."""
    notes: list[str] = []
    surplus = f.median_monthly_net_surplus or 0.0

    # Drawings allowance for proprietorships (owner draws for living expenses;
    # not free debt capacity).
    if rec.entity.reg_type == RegType.PROPRIETORSHIP:
        drawings = max(0.0, surplus) * PROPRIETOR_DRAWINGS_FRACTION
        surplus -= drawings
        if drawings > 0:
            notes.append(f"Drawings allowance ({int(PROPRIETOR_DRAWINGS_FRACTION*100)}%) deducted "
                         f"for proprietorship.")

    existing_service = f.observed_monthly_debt_service or 0.0
    surplus = max(0.0, surplus)

    if surplus <= 0:
        return LoanSizing(0.0, 0.0, 0.0, 0.0, 0.0,
                          notes + ["No positive net surplus — no indicative headroom."])

    # Post-loan DSCR target: surplus must cover (existing + new) service at >= target.
    # Use the midpoint of the target band for sizing.
    target_dscr = (TARGET_POST_LOAN_DSCR_MIN + TARGET_POST_LOAN_DSCR_MAX) / 2.0
    # Available service budget for the NEW loan: surplus/target - existing service.
    new_service_budget = surplus / target_dscr - existing_service
    if new_service_budget <= 0:
        return LoanSizing(0.0, 0.0, surplus, 0.0, 0.0,
                          notes + ["Existing obligations already consume available surplus "
                                   "at the target DSCR."])

    principal = _max_principal_for_emi(new_service_budget, ASSUMED_ANNUAL_RATE, DEFAULT_TENOR_MONTHS)

    # Volatility haircut from inflow CV.
    cv = f.inflow_cv or 0.0
    vol_haircut = min(MAX_VOLATILITY_HAIRCUT, VOLATILITY_HAIRCUT_K * cv)
    principal *= (1.0 - vol_haircut)
    if vol_haircut > 0:
        notes.append(f"Volatility haircut {int(vol_haircut*100)}% (inflow CV {round(cv,2)}).")

    # Concentration haircut.
    conc_haircut = 0.0
    if (f.top1_payer_share or 0) >= CONCENTRATION_TOP1_THRESHOLD or \
       (f.top3_payer_share or 0) >= CONCENTRATION_TOP3_THRESHOLD:
        conc_haircut = CONCENTRATION_HAIRCUT
        principal *= (1.0 - conc_haircut)
        notes.append(f"Concentration haircut {int(conc_haircut*100)}% "
                     f"(top payer {round((f.top1_payer_share or 0)*100)}%).")

    # Round to a clean indicative figure (nearest 25k, floored).
    limit = float(int(principal // 25_000) * 25_000)

    # Report the resulting post-loan DSCR at this limit.
    new_emi = _emi(limit, ASSUMED_ANNUAL_RATE, DEFAULT_TENOR_MONTHS) if limit > 0 else 0.0
    denom = max(existing_service + new_emi, 1.0)   # floor denominator
    post_dscr = min(DSCR_CAP, surplus / denom)

    return LoanSizing(
        indicative_limit=limit,
        post_loan_dscr=round(post_dscr, 2),
        monthly_surplus_used=round(surplus, 0),
        volatility_haircut=round(vol_haircut, 3),
        concentration_haircut=round(conc_haircut, 3),
        notes=notes,
    )


# Severity ordering — gates may only move the outcome to a MORE conservative
# decision, never rescue a worse one (a soft refer never upgrades a band-D decline).
_SEVERITY = {Decision.APPROVE: 0, Decision.REFER: 1, Decision.DECLINE: 2}


def decide(rec: CanonicalRecord, f: Features, score: ScoreResult,
           outcome: PipelineOutcome) -> DecisionResult:
    """Decide by taking the MOST CONSERVATIVE of (band policy, gate verdicts).

    Precedence is monotone in severity: a hard-gate decline always wins; a refer
    gate can only pull an approve down to refer; neither can lift a decline.
    """
    band = score.band
    fhs = score.fhs

    # Base decision from band policy.
    policy = BAND_DECISION.get(band, "decline")
    base = Decision(policy)
    rationale = f"band:{band}"
    blocking_gate: Optional[str] = None

    # Hard gate declines (consent / bureau hard markers / fraud veto) dominate.
    if outcome.hard_declined:
        gate = outcome.blocking_gate()
        if _SEVERITY[Decision.DECLINE] > _SEVERITY[base]:
            base, rationale, blocking_gate = Decision.DECLINE, f"hard-gate:{gate}", gate
        else:
            blocking_gate = gate  # already declining on band; record the gate too

    # Soft refer gates pull an approve down to refer (never lift a decline).
    elif outcome.must_refer:
        refer_gate = next((g.name for g in (outcome.sufficiency, outcome.fraud, outcome.bureau)
                           if g.status == GateStatus.REFER), None)
        if _SEVERITY[Decision.REFER] > _SEVERITY[base]:
            base, rationale = Decision.REFER, f"gate-refer:{refer_gate}"

    # Size the loan only on a genuine approve.
    if base == Decision.APPROVE:
        sizing = size_loan(rec, f)
        if sizing.indicative_limit <= 0:
            return DecisionResult(Decision.REFER, band, fhs, sizing,
                                  rationale="approve-band-no-headroom", blocking_gate=None)
        return DecisionResult(Decision.APPROVE, band, fhs, sizing,
                              rationale=rationale, blocking_gate=None)

    return DecisionResult(base, band, fhs, None, rationale=rationale,
                          blocking_gate=blocking_gate)
