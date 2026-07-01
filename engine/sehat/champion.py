"""Champion scorecard — serve-time inference (deterministic, no ML deps).

The champion is a WOE + logistic-regression scorecard: bank-standard, fully
readable, and the formal statistical model of record. It is TRAINED offline by
`scripts/train_models.py` (which writes `artifacts/champion.json`) and SERVED here
by a pure lookup + dot-product — exactly the "deterministic at inference, learned
from data" property the deck argues makes it deployable where a black box is not.

This module imports only numpy (already a serve dependency). It NEVER imports
sklearn / lightgbm / shap — those are training-only. If champion.json is absent
(models not trained yet) the API degrades gracefully: the loader returns None and
the cross-check is simply omitted, never erroring the card.

Scorecard points (Siddiqi standard): higher points = safer.
  factor = pdo / ln(2);  offset = base_points - factor*ln(base_odds)
  total  = offset - factor*logit         (logit = ln odds-of-default)
  pointsᵢ = -(coefᵢ·woeᵢ)·factor  -  factor·intercept/n  +  offset/n   (Σ = total)
The points are a monotone affine view of the PD — presentation only; the PD and
the agreement decision do not depend on the anchors.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sehat.model_features import FEATURE_DOMAIN, FEATURE_LABEL, extract_vector
from sehat.features import Features

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
CHAMPION_PATH = ARTIFACTS / "champion.json"


@dataclass
class Contribution:
    """One feature's contribution to the champion's score."""
    key: str
    label: str
    domain: str
    value: Optional[float]   # raw feature value (None if missing -> neutral bin)
    woe: float
    points: float            # scorecard points (higher = safer); signed
    missing: bool

    def to_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label, "domain": self.domain,
            "value": (round(self.value, 4) if self.value is not None else None),
            "woe": round(self.woe, 4), "points": round(self.points, 1),
            "missing": self.missing,
        }


@dataclass
class ChampionResult:
    pd: float                       # probability of default (0..1)
    score_points: float             # total scorecard points (higher = safer)
    approve: bool                   # PD <= frozen threshold
    threshold: float                # frozen approve threshold (PD)
    contributions: list[Contribution]
    model_version: str

    def to_dict(self) -> dict:
        return {
            "pd": round(self.pd, 4),
            "score_points": round(self.score_points, 1),
            "approve": self.approve,
            "threshold": round(self.threshold, 4),
            "contributions": [c.to_dict() for c in self.contributions],
            "model_version": self.model_version,
        }


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _woe_lookup(value: Optional[float], spec: dict) -> tuple[float, bool]:
    """Return (woe, missing). Mirrors woe.WOEFeature.woe_of without importing it."""
    if value is None:
        return float(spec["missing_woe"]), True
    for b in spec["bins"]:
        if b["lo"] <= value < b["hi"]:
            return float(b["woe"]), False
    bins = spec["bins"]
    return (float(bins[-1]["woe"]) if bins else 0.0), False


class Champion:
    """Loaded, frozen champion scorecard. Construct via `load()` (cached)."""

    def __init__(self, blob: dict):
        self.version: str = blob["model_version"]
        self.intercept: float = float(blob["intercept"])
        self.features: list[dict] = blob["features"]   # ordered; each has key, coef, bins...
        self.threshold: float = float(blob["approve_threshold_pd"])
        sc = blob["scaling"]
        self.pdo: float = float(sc["pdo"])
        self.base_points: float = float(sc["base_points"])
        self.base_odds: float = float(sc["base_odds"])
        self._factor = self.pdo / math.log(2.0)
        self._offset = self.base_points - self._factor * math.log(self.base_odds)
        self._n = len(self.features)

    def score(self, f: Features) -> ChampionResult:
        values = extract_vector(f)
        logit = self.intercept
        per_feature: list[tuple[dict, float, Optional[float], bool]] = []
        for spec in self.features:
            key = spec["key"]
            val = values.get(key)
            woe, missing = _woe_lookup(val, spec)
            logit += float(spec["coef"]) * woe
            per_feature.append((spec, woe, val, missing))

        pd = _sigmoid(logit)
        total_points = self._offset - self._factor * logit

        contribs: list[Contribution] = []
        for spec, woe, val, missing in per_feature:
            coef = float(spec["coef"])
            pts = -(coef * woe) * self._factor \
                  - self._factor * self.intercept / self._n \
                  + self._offset / self._n
            key = spec["key"]
            contribs.append(Contribution(
                key=key, label=FEATURE_LABEL.get(key, key),
                domain=FEATURE_DOMAIN.get(key, ""), value=val, woe=woe,
                points=pts, missing=missing,
            ))
        # Most decision-relevant first: largest absolute deviation from a neutral
        # (mean) point contribution. A neutral bin (woe 0) lands near the mean.
        mean_pts = total_points / self._n if self._n else 0.0
        contribs.sort(key=lambda c: abs(c.points - mean_pts), reverse=True)

        return ChampionResult(
            pd=pd, score_points=total_points, approve=(pd <= self.threshold),
            threshold=self.threshold, contributions=contribs, model_version=self.version,
        )


@lru_cache(maxsize=1)
def load(path: str | Path = CHAMPION_PATH) -> Optional[Champion]:
    """Load the frozen champion. Returns None if not trained yet (graceful degrade)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return Champion(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, OSError):
        return None
