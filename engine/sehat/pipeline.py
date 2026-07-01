"""Pre-score pipeline — the gates that wrap the scoring engine.

Order (each can veto/cap; all run BEFORE the credit decision is finalised):
  1. Consent artefact check   — refuse to score without a valid, unexpired,
     in-scope ReBIT consent.
  2. Data-sufficiency gate     — require >=6mo txns and >=2 GST returns, else
     REFER (insufficient data); CV/trend/seasonality are meaningless below this.
  3. Fraud / anti-gaming layer — round-tripping, recency-spike, payer-concentration,
     GST integrity. Can CAP a sub-score (e.g. revenue trend) or VETO outright.
  4. Bureau / hygiene hard-gate— SMA / write-off / settlement / willful-default /
     enquiry velocity -> decline/refer REGARDLESS of FHS.

The pipeline returns a `PipelineOutcome` describing what happened at each gate
and any caps the scoring layer must apply. It does NOT itself score — the
orchestrator in `engine.py` runs gates, applies caps, scores, then the decision
layer reads the gate verdicts. Each gate emits canonical reason codes only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from sehat.config import (
    GST_EFFECTIVE_TAX_FLOOR,
    GST_INTEGRITY_INFLOW_OVER_TURNOVER,
    MIN_GST_RETURNS,
    MIN_TXN_MONTHS,
    RECENCY_SPIKE_RATIO,
    ROUND_TRIP_MIN_GROSS,
    ROUND_TRIP_NET_RATIO,
)
from sehat.features import Features
from sehat.schema import CanonicalRecord, FIType, TxnType
from sehat.scoring import ReasonHit

AS_OF = date(2026, 6, 29)


class GateStatus(str, Enum):
    PASS = "pass"
    REFER = "refer"
    DECLINE = "decline"


@dataclass
class GateResult:
    name: str
    status: GateStatus
    reasons: list[ReasonHit] = field(default_factory=list)
    # Sub-score caps this gate imposes (only the fraud gate uses these today).
    caps: dict[str, float] = field(default_factory=dict)


@dataclass
class PipelineOutcome:
    consent: GateResult
    sufficiency: GateResult
    fraud: GateResult
    bureau: GateResult
    # Caps the scoring layer must apply (subscore name -> max value 0..100).
    subscore_caps: dict[str, float] = field(default_factory=dict)

    @property
    def hard_declined(self) -> bool:
        return any(g.status == GateStatus.DECLINE
                   for g in (self.consent, self.sufficiency, self.fraud, self.bureau))

    @property
    def must_refer(self) -> bool:
        return any(g.status == GateStatus.REFER
                   for g in (self.consent, self.sufficiency, self.fraud, self.bureau))

    @property
    def gate_reasons(self) -> list[ReasonHit]:
        out: list[ReasonHit] = []
        for g in (self.consent, self.sufficiency, self.fraud, self.bureau):
            out.extend(g.reasons)
        return out

    def blocking_gate(self) -> Optional[str]:
        for g in (self.consent, self.bureau, self.sufficiency, self.fraud):
            if g.status == GateStatus.DECLINE:
                return g.name
        return None


# ---------------------------------------------------------------------------
# Gate 1: Consent artefact
# ---------------------------------------------------------------------------
def check_consent(rec: CanonicalRecord, as_of: date = AS_OF) -> GateResult:
    c = rec.consent
    if c is None:
        return GateResult("consent", GateStatus.DECLINE, [ReasonHit("CN_MISSING", {})])
    if not c.is_valid_on(as_of):
        return GateResult("consent", GateStatus.DECLINE,
                          [ReasonHit("CN_EXPIRED", {"consent_id": c.consent_id,
                                                    "expiry": c.consent_expiry.isoformat()})])
    # The data we actually hold must be covered by consent scope.
    required: list[FIType] = []
    if rec.txns:
        required.append(FIType.DEPOSIT)
    if rec.gst_returns:
        required.append(FIType.GST_RETURNS)
    if rec.upi:
        required.append(FIType.UPI)
    missing = c.covers(required)
    if missing:
        return GateResult("consent", GateStatus.DECLINE,
                          [ReasonHit("CN_SCOPE_MISMATCH",
                                     {"missing": ", ".join(m.value for m in missing)})])
    return GateResult("consent", GateStatus.PASS,
                      [ReasonHit("CN_VALID", {"consent_id": c.consent_id,
                                              "purpose": c.purpose_text,
                                              "expiry": c.consent_expiry.isoformat()})])


# ---------------------------------------------------------------------------
# Gate 2: Data sufficiency
# ---------------------------------------------------------------------------
def check_sufficiency(rec: CanonicalRecord, f: Features) -> GateResult:
    reasons: list[ReasonHit] = []
    insufficient = False
    if f.txn_months < MIN_TXN_MONTHS:
        insufficient = True
        reasons.append(ReasonHit("DS_INSUFFICIENT_TXN",
                                 {"txn_months": f.txn_months, "min_months": MIN_TXN_MONTHS}))
    if f.gst_returns < MIN_GST_RETURNS:
        insufficient = True
        reasons.append(ReasonHit("DS_INSUFFICIENT_GST",
                                 {"gst_returns": f.gst_returns, "min_returns": MIN_GST_RETURNS}))
    if insufficient:
        return GateResult("sufficiency", GateStatus.REFER, reasons)
    if f.any_reweighted_marker():
        reasons.append(ReasonHit("DS_REWEIGHTED", {}))
    return GateResult("sufficiency", GateStatus.PASS, reasons)


# Helper bolted onto Features at runtime (kept here to avoid a features import cycle).
def _any_reweighted_marker(self: Features) -> bool:
    # Some primary source missing => the score will be reweighted.
    return not (self.has_txns and self.has_gst and self.has_upi)


Features.any_reweighted_marker = _any_reweighted_marker  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Gate 3: Fraud / anti-gaming
# ---------------------------------------------------------------------------
def check_fraud(rec: CanonicalRecord, f: Features) -> GateResult:
    """Returns a GateResult whose `caps` field carries any sub-score caps."""
    reasons: list[ReasonHit] = []
    caps: dict[str, float] = {}
    status = GateStatus.PASS

    # 3a. Round-tripping: per counterparty, large gross flow that nets ~zero.
    by_cp: dict[str, list[float]] = {}
    for t in rec.txns:
        if t.counterparty_id is None:
            continue
        by_cp.setdefault(t.counterparty_id, []).append(t.signed_amount)
    for cp, flows in by_cp.items():
        gross = sum(abs(x) for x in flows)
        net = abs(sum(flows))
        if gross >= ROUND_TRIP_MIN_GROSS and gross > 0 and (net / gross) <= ROUND_TRIP_NET_RATIO:
            status = GateStatus.REFER
            reasons.append(ReasonHit("FR_ROUND_TRIPPING",
                                     {"gross": f"{int(gross):,}", "counterparty": cp}))
            # Wash inflows inflate cash-flow & revenue — cap both.
            caps["cash_flow"] = min(caps.get("cash_flow", 100.0), 55.0)
            caps["revenue_vitality"] = min(caps.get("revenue_vitality", 100.0), 60.0)

    # 3b. Recency spike: last-90d mean inflow >> trailing baseline -> cap trend.
    if f.recent_inflow_mean and f.baseline_inflow_mean and f.baseline_inflow_mean > 0:
        ratio = f.recent_inflow_mean / f.baseline_inflow_mean
        if ratio >= RECENCY_SPIKE_RATIO:
            reasons.append(ReasonHit("FR_RECENCY_SPIKE",
                                     {"recent_mean": f"{int(f.recent_inflow_mean):,}",
                                      "ratio": round(ratio, 1)}))
            caps["revenue_vitality"] = min(caps.get("revenue_vitality", 100.0), 55.0)
            if status == GateStatus.PASS:
                status = GateStatus.REFER

    # 3c. Payer concentration despite high unique-payer count.
    if f.top1_payer_share is not None and f.unique_counterparties is not None:
        if f.top1_payer_share >= 0.5 and f.unique_counterparties >= 30:
            reasons.append(ReasonHit("FR_PAYER_CONCENTRATION", {}))
            caps["digital_footprint"] = min(caps.get("digital_footprint", 100.0), 50.0)

    # 3d. GST integrity: observed inflow materially exceeds declared turnover.
    if f.gst_inflow_alignment is not None and f.gst_inflow_alignment >= GST_INTEGRITY_INFLOW_OVER_TURNOVER:
        reasons.append(ReasonHit("FR_GST_INTEGRITY", {"ratio": round(f.gst_inflow_alignment, 2)}))
        caps["revenue_vitality"] = min(caps.get("revenue_vitality", 100.0), 60.0)
        if status == GateStatus.PASS:
            status = GateStatus.REFER

    # 3e. GST nil-tax: turnover declared but effectively no tax paid across periods.
    total_turnover = sum(g.turnover for g in rec.gst_returns)
    total_tax = sum(g.tax_paid for g in rec.gst_returns)
    if total_turnover > 0 and (total_tax / total_turnover) < GST_EFFECTIVE_TAX_FLOOR:
        reasons.append(ReasonHit("FR_GST_NIL_TAX", {}))
        caps["compliance"] = min(caps.get("compliance", 100.0), 50.0)

    if not reasons:
        reasons.append(ReasonHit("FR_CLEAR", {}))

    return GateResult("fraud", status, reasons, caps=caps)


# ---------------------------------------------------------------------------
# Gate 4: Bureau / hygiene hard-gate
# ---------------------------------------------------------------------------
def check_bureau(rec: CanonicalRecord) -> GateResult:
    b = rec.bureau
    if b is None or not b.bureau_file:
        # Thin/no bureau file is NOT a decline — it's the whole point. Note it
        # honestly; Sehat assesses on alternate data instead.
        return GateResult("bureau", GateStatus.PASS, [ReasonHit("BG_THIN_FILE", {})])

    reasons: list[ReasonHit] = []
    # Hard declines (necessary-but-insufficient: clean bureau doesn't approve, but
    # a delinquent bureau DECLINES regardless of FHS).
    if b.willful_defaulter:
        return GateResult("bureau", GateStatus.DECLINE, [ReasonHit("BG_WILLFUL", {})])
    if b.recent_writeoff or b.settlement:
        return GateResult("bureau", GateStatus.DECLINE, [ReasonHit("BG_WRITEOFF", {})])
    if b.sma_status and b.sma_status >= 1:
        return GateResult("bureau", GateStatus.DECLINE,
                          [ReasonHit("BG_SMA", {"sma": b.sma_status})])

    # Soft signal: high enquiry velocity -> refer (not decline).
    status = GateStatus.PASS
    if b.enquiries_6m >= 6:
        status = GateStatus.REFER
        reasons.append(ReasonHit("BG_ENQUIRY_VELOCITY", {"enquiries": b.enquiries_6m}))
    reasons.append(ReasonHit("BG_PASS", {}))
    return GateResult("bureau", status, reasons)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_pipeline(rec: CanonicalRecord, f: Features, as_of: date = AS_OF) -> PipelineOutcome:
    consent = check_consent(rec, as_of)
    sufficiency = check_sufficiency(rec, f)
    fraud_result = check_fraud(rec, f)
    bureau = check_bureau(rec)
    return PipelineOutcome(
        consent=consent,
        sufficiency=sufficiency,
        fraud=fraud_result,
        bureau=bureau,
        subscore_caps=dict(fraud_result.caps),
    )
