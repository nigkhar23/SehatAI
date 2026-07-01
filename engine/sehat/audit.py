"""Immutable per-decision audit record (audit should-add).

Every assessment produces an `AuditRecord`: a tamper-evident snapshot of exactly
what the engine saw and decided, suitable for a bank's model-governance trail.

Captured: timestamp, entity id, consent id, scorecard version, a hash of the
canonical input (so the inputs can be proven unchanged without storing PII), the
six sub-scores, every reason code emitted, the FHS/band/decision/limit, and the
LLM model + prompt version used for narration (provenance — even though narration
is pre-generated offline). The record is content-addressed by its own hash.

This module computes the record; persistence is a thin append-only writer so the
deployed app can log decisions to disk/JSONL. Records are never mutated in place;
re-scoring a re-fit scorecard produces a NEW record under a new version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from sehat.config import NARRATION_MODEL_ID, NARRATION_PROMPT_VERSION, SCORECARD_VERSION
from sehat.schema import CanonicalRecord


def canonical_input_hash(rec: CanonicalRecord) -> str:
    """Stable SHA-256 over the scoring input (label stripped). Order-independent
    via sorted JSON keys, so the same inputs always hash the same."""
    payload = rec.for_scoring().model_dump(mode="json")
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class AuditRecord:
    timestamp: str                      # caller-supplied ISO ts (Date.now() banned in engine)
    entity_id: str
    consent_id: Optional[str]
    scorecard_version: str
    input_hash: str
    subscores: dict[str, float]
    effective_weights: dict[str, float]
    reason_codes: list[str]
    gate_reason_codes: list[str]
    fhs: float
    band: str
    decision: str
    blocking_gate: Optional[str]        # which gate forced a decline/refer (None if band-driven)
    indicative_limit: float
    post_loan_dscr: Optional[float]
    narration_model_id: str
    narration_prompt_version: str
    record_hash: str = ""               # filled by finalize()

    def finalize(self) -> "AuditRecord":
        body = {k: v for k, v in asdict(self).items() if k != "record_hash"}
        blob = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
        self.record_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
        return self


def build_audit_record(
    rec: CanonicalRecord,
    *,
    timestamp: str,
    subscores: dict[str, float],
    effective_weights: dict[str, float],
    reason_codes: list[str],
    gate_reason_codes: list[str],
    fhs: float,
    band: str,
    decision: str,
    indicative_limit: float,
    post_loan_dscr: Optional[float],
    blocking_gate: Optional[str] = None,
) -> AuditRecord:
    return AuditRecord(
        timestamp=timestamp,
        entity_id=rec.entity.id,
        consent_id=rec.consent.consent_id if rec.consent else None,
        scorecard_version=SCORECARD_VERSION,
        input_hash=canonical_input_hash(rec),
        subscores=subscores,
        effective_weights=effective_weights,
        reason_codes=reason_codes,
        gate_reason_codes=gate_reason_codes,
        fhs=fhs,
        band=band,
        decision=decision,
        blocking_gate=blocking_gate,
        indicative_limit=indicative_limit,
        post_loan_dscr=post_loan_dscr,
        narration_model_id=NARRATION_MODEL_ID,
        narration_prompt_version=NARRATION_PROMPT_VERSION,
    ).finalize()


class AuditLog:
    """Append-only JSONL writer. Never edits existing lines (immutability)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: AuditRecord) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), default=str))
            fh.write("\n")
