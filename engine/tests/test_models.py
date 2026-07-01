"""Hybrid-model tests — the learned champion + challenger guarantees, in code.

These assert the properties the deck and OVERVIEW_PLAIN claim for the upgrade:
  1. WOE binning is MONOTONE in each feature's good-direction (no "more bounces ->
     safer"), and Information Value is non-negative.
  2. The champion serves DETERMINISTICALLY from the frozen champion.json (same
     features -> identical PD), and is monotone (a uniformly-worse applicant never
     gets a lower PD).
  3. The frozen per-persona model_explain block reconstructs: champion PD recomputed
     live == frozen champion PD; challenger SHAP + base == challenger margin.
  4. The cross-check agreement logic is correct (agree iff all available views match).

WOE/champion tests need only numpy (always present). The SHAP-reconstruction test is
SKIPPED if lightgbm/shap aren't installed (they're dev-only) — it validates the
offline freezing step, not the serve path.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from sehat.challenger import cross_check
from sehat.champion import load as load_champion
from sehat.features import Features
from sehat.model_features import FEATURE_KEYS
from sehat.woe import fit_feature

ENGINE = Path(__file__).resolve().parent.parent
ARTIFACTS = ENGINE / "artifacts"
PERSONAS = ENGINE / "personas"


# ---------------------------------------------------------------------------
# 1. WOE binning
# ---------------------------------------------------------------------------
def test_woe_is_monotone_in_good_direction():
    """A +1 feature: higher value -> higher WOE (safer). Synthesize a clean signal."""
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 10, 600)
    # Higher x => lower default probability (a +1 'good' feature).
    p = 1.0 / (1.0 + np.exp(0.8 * (x - 5)))
    y = (rng.uniform(0, 1, 600) < p).astype(int)
    wf = fit_feature("synthetic_up", x, y, good_direction=+1)
    woes = [b.woe for b in wf.bins]
    assert wf.monotone
    assert all(woes[i] <= woes[i + 1] + 1e-9 for i in range(len(woes) - 1))
    assert wf.iv > 0.0


def test_woe_monotone_down_feature():
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 1, 600)
    # Higher x => HIGHER default (a -1 'bad' feature, e.g. bounce rate).
    p = 1.0 / (1.0 + np.exp(-3.0 * (x - 0.5)))
    y = (rng.uniform(0, 1, 600) < p).astype(int)
    wf = fit_feature("synthetic_down", x, y, good_direction=-1)
    woes = [b.woe for b in wf.bins]
    assert wf.monotone
    # Non-increasing for a -1 feature.
    assert all(woes[i] >= woes[i + 1] - 1e-9 for i in range(len(woes) - 1))


def test_woe_missing_is_neutral():
    """Missing values map to a NEUTRAL bin (WOE 0) — absence is never a penalty."""
    rng = np.random.default_rng(2)
    x = rng.uniform(0, 10, 200)
    y = (rng.uniform(0, 1, 200) < 0.2).astype(int)
    wf = fit_feature("with_missing", x, y, good_direction=+1)
    assert wf.missing_woe == 0.0
    assert wf.woe_of(None) == 0.0


# ---------------------------------------------------------------------------
# 2. Champion serve-time
# ---------------------------------------------------------------------------
def _baseline_features() -> Features:
    f = Features()
    f.has_txns = f.has_gst = f.has_upi = True
    f.inflow_cv = 0.2
    f.surplus_ratio = 0.22
    f.runway_months = 3.5
    f.turnover_slope_pct = 12.0
    f.seasonality = 1.8
    f.bounce_rate = 0.0
    f.neg_balance_days = 0
    f.median_balance = 250_000.0
    f.filing_ontime_pct = 90.0
    f.vintage_months = 40
    f.dscr_proxy = 1.8
    f.obligation_ratio = 0.15
    f.txn_velocity = 30.0
    f.unique_counterparties = 35
    f.top1_payer_share = 0.2
    return f


champion_required = pytest.mark.skipif(
    not (ARTIFACTS / "champion.json").exists(),
    reason="champion.json not trained (run scripts/train_models.py)",
)


@champion_required
def test_champion_is_deterministic():
    champ = load_champion()
    f = _baseline_features()
    a, b = champ.score(f), champ.score(f)
    assert a.pd == b.pd
    assert a.score_points == b.score_points
    assert [c.key for c in a.contributions] == [c.key for c in b.contributions]


@champion_required
def test_champion_pd_monotone_under_uniform_worsening():
    """A uniformly-worse applicant must not get a LOWER PD (champion is monotone)."""
    champ = load_champion()
    good = champ.score(_baseline_features()).pd

    worse = _baseline_features()
    worse.inflow_cv = 0.9
    worse.surplus_ratio = -0.05
    worse.runway_months = 0.3
    worse.turnover_slope_pct = -30.0
    worse.seasonality = 6.0
    worse.bounce_rate = 0.2
    worse.neg_balance_days = 20
    worse.median_balance = 1_000.0
    worse.filing_ontime_pct = 30.0
    worse.vintage_months = 5
    worse.dscr_proxy = 0.8
    worse.obligation_ratio = 0.6
    worse.txn_velocity = 3.0
    worse.unique_counterparties = 3
    worse.top1_payer_share = 0.9
    assert champ.score(worse).pd >= good - 1e-9


@champion_required
def test_champion_coefs_all_nonpositive():
    """Sign constraint: WOE is risk-aligned, so every coefficient must be <= 0
    (no 'higher WOE -> riskier'). Read straight from the frozen artifact."""
    blob = json.loads((ARTIFACTS / "champion.json").read_text(encoding="utf-8"))
    assert all(feat["coef"] <= 1e-9 for feat in blob["features"])


# ---------------------------------------------------------------------------
# 3. Frozen per-persona consistency (champion recompute == frozen)
# ---------------------------------------------------------------------------
@champion_required
def test_frozen_champion_matches_live_recompute():
    """Every persona's frozen champion PD must equal a live recompute from the
    same record — the determinism the audit/cross-check depends on."""
    from sehat.engine import assess
    from sehat.schema import CanonicalRecord

    champ = load_champion()
    persona_files = sorted(PERSONAS.glob("*.json"))
    assert persona_files, "no personas found"
    for path in persona_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        me = data.get("model_explain")
        if not me:
            continue  # not frozen yet
        rec = CanonicalRecord.model_validate(data["record"])
        a = assess(rec, timestamp="2026-06-29T00:00:00Z")
        live = champ.score(a.features)
        frozen_pd = me["champion"]["pd"]
        assert abs(live.pd - frozen_pd) < 1e-3, f"{path.name}: live {live.pd} != frozen {frozen_pd}"


def test_shap_reconstructs_margin():
    """SHAP attributions + base must reconstruct the challenger's margin (the
    correctness invariant of the offline freezing step). Dev-only deps -> skip if
    absent."""
    lgb = pytest.importorskip("lightgbm")
    shap = pytest.importorskip("shap")
    if not (ARTIFACTS / "challenger.txt").exists():
        pytest.skip("challenger.txt not trained")

    import warnings

    from sehat.engine import assess
    from sehat.model_features import extract_vector
    from sehat.schema import CanonicalRecord

    booster = lgb.Booster(model_file=str(ARTIFACTS / "challenger.txt"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        explainer = shap.TreeExplainer(booster)

    persona_files = sorted(PERSONAS.glob("*.json"))
    for path in persona_files[:3]:
        data = json.loads(path.read_text(encoding="utf-8"))
        rec = CanonicalRecord.model_validate(data["record"])
        a = assess(rec, timestamp="2026-06-29T00:00:00Z")
        vec = extract_vector(a.features)
        X = np.array([[vec[k] if vec[k] is not None else np.nan for k in FEATURE_KEYS]],
                     dtype=float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sv = explainer.shap_values(X)
        if isinstance(sv, list):
            sv = sv[-1]
        contrib = np.asarray(sv)[0]
        base = float(np.atleast_1d(explainer.expected_value)[-1])
        margin = float(booster.predict(X, raw_score=True)[0])
        assert abs((base + contrib.sum()) - margin) < 1e-4


# ---------------------------------------------------------------------------
# 4. Cross-check agreement logic
# ---------------------------------------------------------------------------
def test_cross_check_all_agree_approve():
    xc = cross_check(fhs_approve=True, champion_approve=True, challenger_approve=True)
    assert xc.agree and "high confidence" in xc.note


def test_cross_check_all_agree_decline():
    xc = cross_check(fhs_approve=False, champion_approve=False, challenger_approve=False)
    assert xc.agree


def test_cross_check_disagreement_flags_review():
    xc = cross_check(fhs_approve=False, champion_approve=False, challenger_approve=True)
    assert not xc.agree and "human review" in xc.note


def test_cross_check_single_signal_not_meaningful():
    xc = cross_check(fhs_approve=True, champion_approve=None, challenger_approve=None)
    assert xc.agree and "not applicable" in xc.note
