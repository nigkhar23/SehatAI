"""Model feature spec — the curated raw features the learned models train on.

THE HYBRID UPGRADE (CLAUDE.md "AI/ML-driven question"). The FHS engine turns each
raw signal into a sub-score via a HAND-SET monotone ramp (e.g. inflow_cv 0.12 -> full
marks, 0.60 -> zero). The learned champion REPLACES those hand-set cut-points with
data-learned ones: it bins each RAW feature by its empirical default rate (WOE) on the
labelled cohort, instead of a human picking the ramp endpoints.

So the models train on the RAW engineered features (this module), NOT on the six
sub-scores — that is what "learn the thresholds from data" actually means. We reuse
`compute_features` as the single source of truth (no formula divergence), and here only
SELECT a curated, monotone, defensible subset and record each feature's GOOD direction.

`good_direction`:  +1  higher value => LOWER risk (e.g. surplus_ratio, runway)
                   -1  higher value => HIGHER risk (e.g. inflow_cv, bounce_rate)
Read directly off the scoring ramps: ramp_up => +1, ramp_down => -1. This same vector
drives (a) monotone WOE binning and (b) the challenger's monotone_constraints, so both
learned models are forbidden — by construction — from the nonsense a black box can learn
("more bounced cheques => safer"). That monotonicity is the deployability argument.

Deliberately EXCLUDED to keep every model feature cleanly monotone:
  * gst_inflow_alignment — non-monotone (risk is U-shaped; peaks near 1.0, and the high
    side is a fraud signal handled by the pipeline, not a creditworthiness gradient).
  * epfo/employee_count — legally-absent for sub-threshold micro MSMEs (NEUTRAL, never a
    penalty); too sparse and too policy-loaded to bin as a risk gradient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sehat.features import Features


@dataclass(frozen=True)
class ModelFeatureSpec:
    """One model feature: where to read it, its direction, and a readable label."""
    key: str                 # attribute on Features
    label: str               # human label for the IV table / SHAP display
    good_direction: int      # +1 higher=better(lower risk), -1 higher=worse
    domain: str              # which sub-score family it belongs to (for grouping)


# Curated, monotone feature set. Order is the canonical column order everywhere
# (training matrix, champion.json, challenger, SHAP) — do not reorder without
# retraining, or frozen artifacts will misalign.
MODEL_FEATURES: tuple[ModelFeatureSpec, ...] = (
    ModelFeatureSpec("inflow_cv",            "Inflow volatility (CV)",        -1, "cash_flow"),
    ModelFeatureSpec("surplus_ratio",        "Operating surplus ratio",       +1, "cash_flow"),
    ModelFeatureSpec("runway_months",        "Liquidity runway (months)",     +1, "cash_flow"),
    ModelFeatureSpec("turnover_slope_pct",   "GST turnover trend",            +1, "revenue_vitality"),
    ModelFeatureSpec("seasonality",          "Seasonality (peak/trough)",     -1, "revenue_vitality"),
    ModelFeatureSpec("bounce_rate",          "Cheque/mandate bounce rate",    -1, "banking_discipline"),
    ModelFeatureSpec("neg_balance_days",     "Days overdrawn",                -1, "banking_discipline"),
    ModelFeatureSpec("median_balance",       "Median EOD balance",            +1, "banking_discipline"),
    ModelFeatureSpec("filing_ontime_pct",    "GST on-time filing %",          +1, "compliance"),
    ModelFeatureSpec("vintage_months",       "Registered vintage (months)",   +1, "compliance"),
    ModelFeatureSpec("obligation_ratio",     "Obligation-to-inflow ratio",    -1, "leverage"),
    ModelFeatureSpec("dscr_proxy",           "DSCR proxy",                    +1, "leverage"),
    ModelFeatureSpec("txn_velocity",         "UPI txn velocity",              +1, "digital_footprint"),
    ModelFeatureSpec("unique_counterparties","Unique counterparties",         +1, "digital_footprint"),
    ModelFeatureSpec("top1_payer_share",     "Top-payer concentration",       -1, "digital_footprint"),
)

FEATURE_KEYS: tuple[str, ...] = tuple(s.key for s in MODEL_FEATURES)
GOOD_DIRECTION: dict[str, int] = {s.key: s.good_direction for s in MODEL_FEATURES}
FEATURE_LABEL: dict[str, str] = {s.key: s.label for s in MODEL_FEATURES}
FEATURE_DOMAIN: dict[str, str] = {s.key: s.domain for s in MODEL_FEATURES}

# Monotone constraint for a P(default) model: a +1 (higher=better) feature must push
# PD DOWN as it rises -> constraint -1; a -1 (higher=worse) feature pushes PD UP -> +1.
# i.e. constraint = -good_direction. Used verbatim by the challenger (LightGBM).
MONOTONE_CONSTRAINTS: list[int] = [-s.good_direction for s in MODEL_FEATURES]


def extract_vector(f: Features) -> dict[str, Optional[float]]:
    """Pull the curated model features off a computed `Features` bundle.

    Returns a dict key -> float|None. None means 'not observable for this entity'
    (e.g. no detected recurring debt -> dscr_proxy is None). The WOE layer maps a
    missing feature to a NEUTRAL contribution (WOE 0), mirroring the FHS engine's
    "reweight, never penalise absence" rule — so a thin/partial file is not punished
    by the learned model any more than by the deterministic one.
    """
    out: dict[str, Optional[float]] = {}
    for key in FEATURE_KEYS:
        v = getattr(f, key, None)
        out[key] = float(v) if v is not None else None
    return out
