"""Challenger model — serve-time view (frozen outputs, no ML deps).

The challenger is a monotonic gradient-boosting model (LightGBM) with SHAP
per-applicant attributions. It is more flexible than the champion (captures mild
curvature/interaction the linear scorecard cannot), so it runs ALONGSIDE as an
independent second opinion — champion DECIDES, challenger ADVISES. The monotone
constraints (from model_features.MONOTONE_CONSTRAINTS) forbid the black-box
nonsense a bank cannot deploy ("more bounces -> safer").

Like the narration, the challenger's per-persona PD + SHAP are PRE-COMPUTED offline
(scripts/pregenerate_model_explain.py) and frozen into the persona JSON, so the
deployed app makes ZERO live model calls and never imports lightgbm/shap. The
challenger's cohort-level AUC + agreement live in artifacts/model_card.json.

This module is therefore pure dataclasses + the agreement rule. It is the contract
between the frozen challenger output and the API payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ShapContribution:
    """One feature's SHAP push on the challenger's log-odds of default.

    `shap` > 0 pushes risk UP; < 0 pushes risk DOWN. We also expose `direction`
    in plain terms for the UI ('increases risk' / 'reduces risk')."""
    key: str
    label: str
    domain: str
    value: Optional[float]
    shap: float

    @property
    def direction(self) -> str:
        return "increases risk" if self.shap > 0 else "reduces risk"

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "domain": self.domain,
                "value": self.value, "shap": round(self.shap, 4),
                "direction": self.direction}


@dataclass
class ChallengerResult:
    pd: float                         # challenger probability of default
    base_value: float                 # SHAP base (cohort mean log-odds, as PD)
    approve: bool                     # PD <= frozen threshold
    threshold: float
    contributions: list[ShapContribution] = field(default_factory=list)
    model_version: str = ""

    def to_dict(self) -> dict:
        return {
            "pd": round(self.pd, 4),
            "base_value": round(self.base_value, 4),
            "approve": self.approve,
            "threshold": round(self.threshold, 4),
            "contributions": [c.to_dict() for c in self.contributions],
            "model_version": self.model_version,
        }

    @classmethod
    def from_frozen(cls, blob: dict) -> "ChallengerResult":
        """Rebuild from the per-persona JSON the offline script froze."""
        contribs = [
            ShapContribution(
                key=c["key"], label=c["label"], domain=c.get("domain", ""),
                value=c.get("value"), shap=float(c["shap"]),
            )
            for c in blob.get("contributions", [])
        ]
        return cls(
            pd=float(blob["pd"]), base_value=float(blob.get("base_value", 0.0)),
            approve=bool(blob["approve"]), threshold=float(blob.get("threshold", 0.5)),
            contributions=contribs, model_version=blob.get("model_version", ""),
        )


# ---------------------------------------------------------------------------
# Agreement — the champion/challenger cross-check the deck leads on.
# ---------------------------------------------------------------------------
@dataclass
class CrossCheck:
    """How the three independent views of this applicant line up.

    `fhs_approve`     — does the deterministic FHS band policy approve? (AA/A)
    `champion_approve`— does the learned WOE scorecard approve? (PD <= threshold)
    `challenger_approve` — does the monotonic GBM approve?
    `agree` is True iff all THREE available views agree on approve-vs-not. When they
    agree -> high confidence; when they disagree -> flag for human review (exactly
    the governance posture a regulator expects: models cross-checked, not blind).
    """
    fhs_approve: Optional[bool]
    champion_approve: Optional[bool]
    challenger_approve: Optional[bool]
    agree: bool
    note: str

    def to_dict(self) -> dict:
        return {
            "fhs_approve": self.fhs_approve,
            "champion_approve": self.champion_approve,
            "challenger_approve": self.challenger_approve,
            "agree": self.agree,
            "note": self.note,
        }


def cross_check(*, fhs_approve: Optional[bool], champion_approve: Optional[bool],
                challenger_approve: Optional[bool]) -> CrossCheck:
    """Combine the available approve-signals into an agreement verdict.

    Robust to any signal being None (model not trained / not applicable): agreement
    is computed over the signals that ARE present, and we never claim agreement on a
    single lone signal."""
    signals = [s for s in (fhs_approve, champion_approve, challenger_approve) if s is not None]
    if len(signals) <= 1:
        agree = True   # nothing to disagree with; not a meaningful cross-check
        note = "Single model available — cross-check not applicable."
    else:
        agree = all(signals) or not any(signals)
        if agree:
            verdict = "approve" if signals[0] else "not-approve"
            note = f"All {len(signals)} models agree ({verdict}) — high confidence."
        else:
            note = "Models disagree — route to human review (governance gate)."
    return CrossCheck(
        fhs_approve=fhs_approve, champion_approve=champion_approve,
        challenger_approve=challenger_approve, agree=agree, note=note,
    )
