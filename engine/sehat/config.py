"""Single source of truth for tunable constants and versioning.

Every magic number the engine relies on lives here so the audit record can pin a
scorecard version to an exact constant set. Weights are FIT (logistic regression
on the labeled cohort) and then written back here rounded — see
`scripts/fit_weights.py`. Nothing downstream hard-codes a weight.
"""

from __future__ import annotations

# --- Versioning -------------------------------------------------------------
# Semver. Bump MINOR when weights are re-fit; never mutate a released version in
# place. The audit record stamps this against every decision.
SCORECARD_VERSION = "1.3.0"   # weights re-fit (ridge + intent-prior shrinkage) on the n=1000 cohort

# Pinned LLM for narration ONLY (short rephrase task; not the flagship). Narration
# is pre-generated offline and shipped as static text — the deployed app makes
# zero live LLM calls. This id is recorded in the audit trail for provenance.
NARRATION_MODEL_ID = "claude-haiku-4-5"
NARRATION_PROMPT_VERSION = "narr-v1"

# --- Sub-score weights (FIT via logistic regression, then rounded) ----------
# Keys must match the six SubScoreName values. Sum == 1.0. These are the rounded,
# interpretable weights; the raw fitted coefficients are recorded in
# artifacts/weight_fit.json. The CLAUDE.md table is the design intent; the fit
# is allowed to move them and DID — document the delta in the validation report.
SUBSCORE_WEIGHTS: dict[str, float] = {
    "cash_flow": 0.21,
    "revenue_vitality": 0.11,
    "banking_discipline": 0.26,
    "compliance": 0.21,
    "leverage": 0.08,
    "digital_footprint": 0.13,
}

# --- Band cutoffs (FHS 0-100) -----------------------------------------------
# Inclusive lower bounds. AA >= 85, A 70-84, B 55-69, C 40-54, D < 40.
BAND_CUTOFFS: list[tuple[str, float]] = [
    ("AA", 85.0),
    ("A", 70.0),
    ("B", 55.0),
    ("C", 40.0),
    ("D", 0.0),
]

# Decision policy by band (before pre-score gates, which can override downward).
BAND_DECISION: dict[str, str] = {
    "AA": "approve",
    "A": "approve",
    "B": "refer",
    "C": "decline",
    "D": "decline",
}

# --- Data-sufficiency gate --------------------------------------------------
MIN_TXN_MONTHS = 6          # CV/trend/seasonality meaningless below this
PREFERRED_TXN_MONTHS = 12
MIN_GST_RETURNS = 2         # absolute floor to compute filing discipline
PREFERRED_GST_RETURNS = 4

# --- Loan sizing ------------------------------------------------------------
# Indicative limit sized so POST-loan DSCR stays in this band. Anchor the exact
# numbers in the Jul 4-5 mentor's language when confirmed.
TARGET_POST_LOAN_DSCR_MIN = 1.30
TARGET_POST_LOAN_DSCR_MAX = 1.50
DSCR_CAP = 3.0              # cap the reported DSCR; floor the denominator
ASSUMED_ANNUAL_RATE = 0.18  # indicative pricing for EMI math on a 36-mo tenor
DEFAULT_TENOR_MONTHS = 36
# Volatility haircut: limit is multiplied by (1 - k*CV), clamped. Higher inflow
# CV -> larger haircut. k chosen so CV=0.5 gives a 25% haircut.
VOLATILITY_HAIRCUT_K = 0.5
MAX_VOLATILITY_HAIRCUT = 0.6
# Concentration modifier: if top-1 payer share exceeds this, haircut the limit.
CONCENTRATION_TOP1_THRESHOLD = 0.40
CONCENTRATION_TOP3_THRESHOLD = 0.70
CONCENTRATION_HAIRCUT = 0.20

# A drawings allowance is subtracted from surplus for proprietorships (owner
# takes money out for living expenses; it is not free debt capacity).
PROPRIETOR_DRAWINGS_FRACTION = 0.15

# --- Fraud / anti-gaming thresholds -----------------------------------------
ROUND_TRIP_NET_RATIO = 0.15      # |net|/gross with a counterparty below this == suspicious wash
ROUND_TRIP_MIN_GROSS = 50_000    # only flag material wash flows
RECENCY_SPIKE_RATIO = 2.0        # last-90d mean inflow >= this * trailing baseline -> cap trend
RECENCY_SPIKE_WINDOW_DAYS = 90
GST_INTEGRITY_INFLOW_OVER_TURNOVER = 1.5  # inflow materially exceeding declared turnover (6-12mo)
GST_EFFECTIVE_TAX_FLOOR = 0.001  # turnover declared but ~zero tax paid across periods -> integrity flag

# --- EPFO ------------------------------------------------------------------
EPFO_MANDATORY_HEADCOUNT = 20    # below this, EPFO absence is NEUTRAL, never a penalty
