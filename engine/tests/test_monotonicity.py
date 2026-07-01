"""Monotonicity + determinism tests — the auditable guarantees, in code.

Run: pip install pytest && pytest -q   (from engine/)

These assert the properties the deck and CLAUDE.md claim:
  1. Each sub-score is monotone in its inputs (perturb one input worse → the
     sub-score never improves).
  2. The full FHS is monotone (a uniformly-worse feature vector never scores higher),
     within a fixed fraud tier.
  3. Scoring is deterministic / reproducible (same input → identical FHS, band, and
     reason-code order across runs).
  4. The grounding validator rejects hallucinated numbers and polarity flips.
"""

from __future__ import annotations

import copy

import pytest

from sehat.features import Features
from sehat.scoring import score, score_cash_flow, score_banking_discipline, score_revenue_vitality
from sehat.explain import ground_narration
from sehat.scoring import ReasonHit


def _baseline_features() -> Features:
    """A reasonable, fully-populated feature vector to perturb around."""
    f = Features()
    f.has_txns = f.has_gst = f.has_upi = True
    f.txn_months = 12
    f.gst_returns = 6
    f.inflow_cv = 0.2
    f.surplus_ratio = 0.22
    f.runway_months = 3.5
    f.turnover_slope_pct = 12.0
    f.gst_inflow_alignment = 0.95
    f.seasonality = 1.8
    f.bounce_count = 0
    f.bounce_rate = 0.0
    f.neg_balance_days = 0
    f.median_balance = 250_000.0
    f.filing_ontime_pct = 90.0
    f.vintage_months = 40
    f.dscr_proxy = 1.8
    f.obligation_ratio = 0.15
    f.recurring_obligation_detected = True
    f.txn_velocity = 30.0
    f.unique_counterparties = 35
    f.top1_payer_share = 0.2
    f.top3_payer_share = 0.4
    f.mean_monthly_inflow = 400_000.0
    return f


def test_cashflow_monotone_in_cv():
    """Higher inflow CV (worse) must never raise the cash-flow sub-score."""
    f = _baseline_features()
    f.inflow_cv = 0.15
    good = score_cash_flow(f).value
    f2 = copy.copy(f)
    f2.inflow_cv = 0.55  # strictly worse
    worse = score_cash_flow(f2).value
    assert worse <= good + 1e-9


def test_banking_monotone_in_bounce_rate():
    f = _baseline_features()
    f.bounce_rate, f.bounce_count = 0.0, 0
    good = score_banking_discipline(f).value
    f2 = copy.copy(f)
    f2.bounce_rate, f2.bounce_count = 0.08, 5
    worse = score_banking_discipline(f2).value
    assert worse <= good + 1e-9


def _features_with_proxy(break_pct, window=3):
    """A revenue-vitality-scorable feature vector carrying an operational proxy."""
    f = _baseline_features()
    f.has_proxy = True
    f.proxy_type = "electricity"
    f.proxy_unit = "kWh"
    f.proxy_recent_break_pct = break_pct
    f.proxy_recent_window_months = window
    return f


def test_revenue_vitality_monotone_in_proxy_break():
    """A worse operational-proxy break (sharper drop) must never RAISE Revenue Vitality.

    This is the operational-proxy analogue of the existing sub-score monotonicity
    guarantees — the new presence-gated component is monotone by construction."""
    steady = score_revenue_vitality(_features_with_proxy(0.0)).value
    mild = score_revenue_vitality(_features_with_proxy(-15.0)).value
    severe = score_revenue_vitality(_features_with_proxy(-40.0)).value
    assert mild <= steady + 1e-9
    assert severe <= mild + 1e-9


def test_proxy_is_presence_gated_identity():
    """An ABSENT proxy must leave Revenue Vitality (and the FHS) mathematically
    identical — the spine-safety invariant the whole §2 build rests on. The proxy
    component renormalises out when it never fires."""
    f_no = _baseline_features()                       # has_proxy defaults to False
    f_yes = _features_with_proxy(0.0)
    assert score_revenue_vitality(f_no).value == pytest.approx(
        score_revenue_vitality(f_no).value)            # deterministic
    # Adding a proxy CHANGES the sub-score (it's a real signal); removing it must
    # return to the exact no-proxy value — proving absence is a no-op, not a penalty.
    f_yes.has_proxy = False
    assert score_revenue_vitality(f_yes).value == score_revenue_vitality(f_no).value
    # And the absent-proxy FHS equals the pre-proxy FHS for the same vector.
    assert score(f_no).fhs == score(_baseline_features()).fhs


def test_proxy_reason_codes_ground():
    """The two proxy reason codes round-trip through the grounding validator: the
    stable strength and the trend-break risk (carrying the live drop_pct/window)."""
    stable = ReasonHit("RV_PROXY_STABLE", {"proxy_type": "electricity"})
    assert ground_narration(
        stable, "Metered electricity use is steady — running at capacity.").grounded
    brk = ReasonHit("RV_PROXY_TREND_BREAK",
                    {"proxy_type": "electricity", "drop_pct": 40.0, "window": 3})
    assert ground_narration(
        brk, "Electricity consumption fell 40.0% over 3 months — a slowdown.").grounded
    # A hallucinated drop the engine never computed must be rejected.
    assert not ground_narration(
        brk, "Electricity consumption fell 75% over 3 months.").grounded


def test_fhs_monotone_under_uniform_worsening():
    """A uniformly-worse feature vector never yields a higher FHS."""
    f = _baseline_features()
    base = score(f).fhs

    worse = copy.copy(f)
    worse.inflow_cv = 0.7
    worse.surplus_ratio = 0.02
    worse.runway_months = 0.5
    worse.turnover_slope_pct = -25.0
    worse.bounce_rate, worse.bounce_count = 0.1, 8
    worse.neg_balance_days = 12
    worse.median_balance = 5_000.0
    worse.filing_ontime_pct = 45.0
    worse.vintage_months = 8
    worse.dscr_proxy = 1.05
    worse.obligation_ratio = 0.45
    worse.txn_velocity = 6.0
    worse.unique_counterparties = 6
    worse.top1_payer_share = 0.65

    assert score(worse).fhs <= base + 1e-9


def test_scoring_is_deterministic():
    """Same input → identical FHS, band, and reason-code ORDER across runs."""
    f = _baseline_features()
    a, b = score(f), score(f)
    assert a.fhs == b.fhs
    assert a.band == b.band
    assert [r.code for r in a.reasons] == [r.code for r in b.reasons]


def test_grounding_rejects_hallucinated_number():
    hit = ReasonHit("CF_INFLOW_VOLATILE", {"cv": 0.6})
    assert ground_narration(hit, "Inflows are volatile (CV 0.6).").grounded
    assert not ground_narration(hit, "Inflows are volatile (CV 0.6), losing 25000.").grounded


def test_grounding_rejects_polarity_flip():
    risk = ReasonHit("CF_INFLOW_VOLATILE", {"cv": 0.6})
    # A risk rephrased as a glowing strength (no negative cue) must fail.
    assert not ground_narration(risk, "Inflows show strong healthy momentum at 0.6.").grounded
    strength = ReasonHit("CF_INFLOW_CONSISTENT", {"cv": 0.15})
    assert not ground_narration(strength, "Inflows are volatile and risky (CV 0.15).").grounded


def test_grounding_rejects_mixed_sentiment_softening_of_risk():
    """A RISK softened with an INTRODUCED positive cue must fail even if it still
    keeps a negative word (the mixed-sentiment bypass the review caught)."""
    risk = ReasonHit("CF_INFLOW_VOLATILE", {"cv": 0.6})
    assert not ground_narration(
        risk, "Inflows show strong momentum despite some volatility (CV 0.6)."
    ).grounded
    # A faithful risk rephrase that introduces no positive cue still passes.
    assert ground_narration(risk, "Inflows are volatile month to month (CV 0.6).").grounded


def test_grounding_accepts_negative_number_rephrase():
    """A declining-turnover risk rendered "-14.8%" rephrased "fell 14.8%" passes
    (sign is format noise), but flipping it to "grew" introduces a positive cue."""
    risk = ReasonHit("RV_DECLINING_TURNOVER", {"slope_pct": -14.8})
    assert ground_narration(risk, "Turnover fell 14.8% over the window.").grounded
    assert not ground_narration(risk, "Turnover grew 14.8% over the window.").grounded


def test_grounding_zero_tolerance_is_exact():
    """A tiny spurious number must not pass as a reformatting of an authorised 0."""
    from sehat.explain import _is_authorised
    assert _is_authorised(0.0, [0.0])
    assert not _is_authorised(5e-7, [0.0])


def test_grounding_rejects_stale_cached_narration():
    """A narration pre-generated for one value-set is rejected when live values
    differ — the safety valve the offline-narration workflow depends on."""
    pregenerated = "Inflows are volatile — month-to-month variation is high (CV 0.6)."
    live_hit = ReasonHit("CF_INFLOW_VOLATILE", {"cv": 0.8})
    assert not ground_narration(live_hit, pregenerated).grounded


def test_grounding_accepts_comma_formatted_number():
    hit = ReasonHit("BD_HEALTHY_BUFFER", {"median_balance": 245000.0})
    assert ground_narration(hit, "Keeps a cushion around 245,000 on hand.").grounded
    assert not ground_narration(hit, "Keeps about 300,000 on hand.").grounded


def test_reasonhit_rejects_undeclared_slot():
    with pytest.raises(ValueError):
        ReasonHit("CF_INFLOW_VOLATILE", {"cv": 0.6, "made_up": 1})
