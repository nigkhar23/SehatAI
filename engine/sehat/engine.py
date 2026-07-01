"""Orchestrator — the single entry point: canonical record -> full assessment.

Flow (deterministic, auditable):
  1. compute_features(rec)
  2. run_pipeline(rec, f)           -> consent / sufficiency / fraud / bureau gates
  3. score(f)                       -> 6 sub-scores + FHS
  4. apply fraud caps to sub-scores -> recompute capped FHS (caps only lower)
  5. decide(...)                    -> approve/refer/decline + indicative limit
  6. build_audit_record(...)        -> immutable governance trail
  7. assemble Assessment            -> everything the UI/API needs

Caps from the fraud gate are applied AFTER scoring and only ever LOWER a value,
so the monotonicity guarantee is preserved (a worse fraud posture never raises a
score). The capped FHS is what the decision and the card use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sehat.audit import AuditRecord, build_audit_record
from sehat.decision import DecisionResult, decide
from sehat.features import Features, compute_features
from sehat.pipeline import PipelineOutcome, run_pipeline
from sehat.scoring import ReasonHit, ScoreResult, band_for, score
from sehat.schema import CanonicalRecord


@dataclass
class Assessment:
    entity_id: str
    features: Features
    outcome: PipelineOutcome
    score: ScoreResult            # post-cap score (the one the card shows)
    raw_score: ScoreResult        # pre-cap score (kept for transparency/audit)
    decision: DecisionResult
    audit: AuditRecord
    # Convenience for the API/UI layer.
    strengths: list[ReasonHit] = field(default_factory=list)
    risks: list[ReasonHit] = field(default_factory=list)


def _apply_caps(raw: ScoreResult, caps: dict[str, float], weights: dict[str, float]) -> ScoreResult:
    """Return a new ScoreResult with capped sub-score values and recomputed FHS.

    Caps only lower values. Reason codes are preserved; the cap itself is surfaced
    via the fraud gate's reason codes, so the card explains why a score is held down.
    """
    if not caps:
        return raw

    from copy import deepcopy

    capped = deepcopy(raw)
    for name, sub in capped.subscores.items():
        if name in caps and sub.available:
            sub.value = min(sub.value, caps[name])

    available = {n: s for n, s in capped.subscores.items() if s.available}
    total_w = sum(weights[n] for n in available) if available else 0.0
    if total_w > 0:
        fhs = sum((weights[n] / total_w) * s.value for n, s in available.items())
    else:
        fhs = 0.0
    capped.fhs = round(fhs, 1)
    capped.band = band_for(fhs)
    return capped


def assess(rec: CanonicalRecord, *, timestamp: str,
           weights: Optional[dict[str, float]] = None) -> Assessment:
    """Run the full pipeline on one canonical record.

    `timestamp` is supplied by the caller (the engine never calls Date.now()).
    """
    from sehat.config import SUBSCORE_WEIGHTS
    weights = weights or SUBSCORE_WEIGHTS

    # Defence in depth: strip any latent label before anything touches the record.
    rec = rec.for_scoring()

    f = compute_features(rec)
    outcome = run_pipeline(rec, f)
    raw = score(f, weights)
    capped = _apply_caps(raw, outcome.subscore_caps, weights)
    decision = decide(rec, f, capped, outcome)

    # Reason codes for the audit trail (post-cap score + gates).
    reason_codes = [r.code for r in capped.reasons]
    gate_codes = [r.code for r in outcome.gate_reasons]

    audit = build_audit_record(
        rec,
        timestamp=timestamp,
        subscores={n: round(s.value, 1) for n, s in capped.subscores.items() if s.available},
        effective_weights=capped.effective_weights,
        reason_codes=reason_codes,
        gate_reason_codes=gate_codes,
        fhs=capped.fhs,
        band=capped.band,
        decision=decision.decision.value,
        blocking_gate=decision.blocking_gate,
        indicative_limit=decision.sizing.indicative_limit if decision.sizing else 0.0,
        post_loan_dscr=decision.sizing.post_loan_dscr if decision.sizing else None,
    )

    from sehat.reason_codes import Polarity
    strengths = [r for r in capped.reasons if r.polarity == Polarity.STRENGTH]
    risks = [r for r in capped.reasons if r.polarity == Polarity.RISK]

    return Assessment(
        entity_id=rec.entity.id,
        features=f,
        outcome=outcome,
        score=capped,
        raw_score=raw,
        decision=decision,
        audit=audit,
        strengths=strengths,
        risks=risks,
    )
