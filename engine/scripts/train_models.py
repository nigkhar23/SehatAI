"""Train the hybrid: champion (WOE+logistic scorecard) + challenger (monotonic GBM).

THE "AI/ML-DRIVEN" UPGRADE (CLAUDE.md / OVERVIEW_PLAIN.md). Two genuinely-trained
models, the way a real bank risk team runs champion/challenger:

  CHAMPION  = WOE binning (data-learned cut-points, replacing the hand-set ramps)
              -> Information Value feature ranking
              -> logistic regression on the WOE values -> a calibrated PD.
              Fully readable, monotone by construction. The model of record.

  CHALLENGER= monotonic LightGBM on the same raw features (monotone constraints from
              model_features.MONOTONE_CONSTRAINTS forbid black-box nonsense), with
              SHAP attributions. Stronger; runs ALONGSIDE as an independent check.

Both train on the RAW engineered features (sehat.model_features), NOT the six
sub-scores — that is what "learn the thresholds from data" means. We reuse the
production `compute_features` (no formula divergence) and the SAME stratified split
as fit_and_validate.py (seed 7, 30% test) so every number is comparable.

Determinism: WOE is RNG-free; LightGBM is pinned (single-thread, deterministic,
fixed seed) so a re-run reproduces the artifacts a judge can clone-and-verify —
exactly the guarantee the FHS fit already gives.

Writes (committed as deck evidence; the cohort itself stays gitignored):
  artifacts/champion.json        — intercept, coefs, WOE bins, scaling, threshold
  artifacts/challenger.txt       — the LightGBM model (dev/offline use only)
  artifacts/model_card.json      — champion vs challenger vs FHS: AUC + agreement + IV

Run:  python scripts/train_models.py    (requires dev deps: scikit-learn lightgbm)
The DEPLOYED engine never imports lightgbm/scikit-learn — champion serves from the
frozen JSON (pure numpy) and the challenger's per-persona outputs are pre-baked.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sehat.features import compute_features
from sehat.model_features import (
    FEATURE_KEYS,
    FEATURE_LABEL,
    MODEL_FEATURES,
    MONOTONE_CONSTRAINTS,
    extract_vector,
)
from sehat.scoring import score
from sehat.sources import MockSource
from sehat.woe import fit_feature

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"

# Scorecard scaling (Siddiqi standard). Presentation only — relative point gaps are
# what's shown; the PD and the cross-check do not depend on these anchors.
PDO = 20.0            # points to double the odds
BASE_POINTS = 600.0   # anchor score
BASE_ODDS = 1.0       # odds (of default) at the anchor -> offset = BASE_POINTS


def _build_matrix(records):
    """Return (X_raw [n,k] with NaN for missing, y, fhs, fhs_approve, thin).

    `fhs` is the UNROUNDED weighted sub-score sum — identical to the reconstruction
    in fit_and_validate.py/validation.py — so the FHS reference AUC in the model card
    matches validation_report.json to the digit (score().fhs rounds to 1dp, which
    would shave AUC by ~0.0001)."""
    from sehat.config import SUBSCORE_WEIGHTS
    X, y, fhs_vals, fhs_appr, thin = [], [], [], [], []
    for rec in records:
        if rec.label is None:
            continue
        f = compute_features(rec.for_scoring())   # no-leak parity with production
        vec = extract_vector(f)
        X.append([vec[k] if vec[k] is not None else np.nan for k in FEATURE_KEYS])
        y.append(1 if rec.label.defaulted_12m else 0)
        sr = score(f)
        avail = {n: s for n, s in sr.subscores.items() if s.available}
        tw = sum(SUBSCORE_WEIGHTS[n] for n in avail)
        fhs_unr = (sum((SUBSCORE_WEIGHTS[n] / tw) * s.value for n, s in avail.items())
                   if tw > 0 else 0.0)
        fhs_vals.append(fhs_unr)
        fhs_appr.append(sr.band in ("AA", "A"))
        thin.append(not (rec.bureau and rec.bureau.bureau_file))
    return (np.array(X, dtype=float), np.array(y, dtype=int),
            np.array(fhs_vals, dtype=float), np.array(fhs_appr, dtype=bool),
            np.array(thin, dtype=bool))


def _threshold_for_rate(pd_scores: np.ndarray, approve_rate: float) -> float:
    """PD cut-off that approves `approve_rate` of the sample (low-PD = approve).

    Aligns each model's operating point to the incumbent FHS approval rate so the
    cross-check compares WHICH applicants are approved, not merely how many."""
    approve_rate = float(min(max(approve_rate, 0.01), 0.99))
    return float(np.quantile(pd_scores, approve_rate))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", default=str(ARTIFACTS / "cohort.jsonl"))
    ap.add_argument("--seed", type=int, default=7)       # match fit_and_validate split
    ap.add_argument("--C", type=float, default=1.0, help="L2 strength for the WOE logistic")
    args = ap.parse_args()

    records = MockSource(args.cohort).all_records()
    X, y, fhs, fhs_appr, thin = _build_matrix(records)
    n, k = X.shape
    idx = np.arange(n)
    tr, te = train_test_split(idx, test_size=0.3, random_state=args.seed, stratify=y)

    # ---- CHAMPION: WOE fit on TRAIN, then logistic on the WOE values ----
    woe_features = []
    iv_rows = []
    for j, spec in enumerate(MODEL_FEATURES):
        wf = fit_feature(spec.key, X[tr, j], y[tr], spec.good_direction)
        woe_features.append(wf)
        iv_rows.append({"key": spec.key, "label": FEATURE_LABEL[spec.key],
                        "iv": round(wf.iv, 4), "monotone": wf.monotone,
                        "n_bins": len(wf.bins)})

    def woe_transform(rows: np.ndarray) -> np.ndarray:
        out = np.zeros((len(rows), k), dtype=float)
        for col, wf in enumerate(woe_features):
            for r, ridx in enumerate(rows):
                val = X[ridx, col]
                out[r, col] = wf.woe_of(None if math.isnan(val) else float(val))
        return out

    W_tr = woe_transform(tr)
    W_te = woe_transform(te)

    # SIGN-CONSTRAINED logistic regression (standard credit-scorecard practice).
    # WOE is risk-aligned (higher WOE -> lower default), so EVERY coefficient must be
    # <= 0. On the correlated WOE features an UNCONSTRAINED logistic flips a few signs
    # (a redundant feature "borrows" the opposite sign of a stronger correlate) — an
    # undeployable scorecard ("higher WOE -> riskier"). Rather than DROP those
    # features, we constrain the optimiser: minimise the L2-penalised negative
    # log-likelihood subject to coef_j <= 0. Collinear features then SHRINK toward 0
    # instead of flipping — so we keep all k features with economically-correct signs.
    # Same philosophy as the FHS weight fit (shrinkage keeps every dimension
    # meaningful AND faithful to the data); here the constraint is a hard sign bound.
    n_clamped, intercept, coefs = _fit_sign_constrained_logit(W_tr, y[tr], C=args.C)

    def champion_pd(W: np.ndarray) -> np.ndarray:
        z = intercept + W @ coefs
        return 1.0 / (1.0 + np.exp(-z))

    pd_tr_champ = champion_pd(W_tr)
    pd_te_champ = champion_pd(W_te)
    champ_thr = _threshold_for_rate(pd_tr_champ, float(fhs_appr[tr].mean()))

    # ---- CHALLENGER: monotonic LightGBM on the RAW features ----
    import lightgbm as lgb

    dtrain = lgb.Dataset(X[tr], label=y[tr], free_raw_data=False)
    params = {
        "objective": "binary",
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_data_in_leaf": 30,
        "max_depth": 4,
        "monotone_constraints": MONOTONE_CONSTRAINTS,
        "monotone_constraints_method": "advanced",
        "feature_fraction": 1.0,
        "bagging_fraction": 1.0,
        "seed": 42,
        "deterministic": True,
        "force_row_wise": True,
        "num_threads": 1,
        "verbose": -1,
    }
    booster = lgb.train(params, dtrain, num_boost_round=300)
    pd_tr_chal = booster.predict(X[tr])
    pd_te_chal = booster.predict(X[te])
    chal_thr = _threshold_for_rate(pd_tr_chal, float(fhs_appr[tr].mean()))

    # ---- Metrics on the held-out TEST slice ----
    auc_champ = float(roc_auc_score(y[te], pd_te_champ))
    auc_chal = float(roc_auc_score(y[te], pd_te_chal))
    auc_fhs = float(roc_auc_score(y[te], 100.0 - fhs[te]))   # matches validation.py

    appr_champ = pd_te_champ <= champ_thr
    appr_chal = pd_te_chal <= chal_thr
    appr_fhs = fhs_appr[te]

    def agree(a, b):
        return float(np.mean(a == b))

    agreement = {
        "champion_vs_challenger": round(agree(appr_champ, appr_chal), 4),
        "champion_vs_fhs": round(agree(appr_champ, appr_fhs), 4),
        "challenger_vs_fhs": round(agree(appr_chal, appr_fhs), 4),
        "all_three": round(float(np.mean((appr_champ == appr_chal) & (appr_chal == appr_fhs))), 4),
        # Rank agreement between the two PDs (does the ordering match, not just the cut)?
        "pd_rank_corr_champ_chal": round(float(np.corrcoef(
            _rankdata(pd_te_champ), _rankdata(pd_te_chal))[0, 1]), 4),
    }

    # ---- Persist champion.json (the serve artifact) ----
    champion_blob = {
        "model_version": "champion-woe-logit-1.0.0",
        "trained_on": {"cohort": Path(args.cohort).name, "n_train": len(tr), "seed": args.seed},
        "intercept": intercept,
        "scaling": {"pdo": PDO, "base_points": BASE_POINTS, "base_odds": BASE_ODDS},
        "approve_threshold_pd": champ_thr,
        "coef_sign_constraint": "all <= 0 (WOE risk-aligned); enforced via L-BFGS-B",
        "n_features_shrunk_to_zero": n_clamped,
        "features": [
            {"key": wf.key, "label": FEATURE_LABEL[wf.key], "coef": float(coefs[i]),
             "good_direction": wf.good_direction, "iv": round(wf.iv, 6),
             "missing_woe": wf.missing_woe,
             "bins": [b.to_dict() for b in wf.bins]}
            for i, wf in enumerate(woe_features)
        ],
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "champion.json").write_text(json.dumps(champion_blob, indent=2), encoding="utf-8")
    booster.save_model(str(ARTIFACTS / "challenger.txt"))

    # ---- Model card (the governance/deck artifact) ----
    iv_rows.sort(key=lambda r: r["iv"], reverse=True)
    model_card = {
        "champion": {
            "type": "WOE binning + logistic regression scorecard",
            "model_version": champion_blob["model_version"],
            "auc": round(auc_champ, 4),
            "approve_threshold_pd": round(champ_thr, 4),
            "coef_sign_constraint": "all <= 0 (WOE risk-aligned)",
            "n_features_shrunk_to_zero": n_clamped,
        },
        "challenger": {
            "type": "Monotonic gradient boosting (LightGBM) + SHAP",
            "auc": round(auc_chal, 4),
            "approve_threshold_pd": round(chal_thr, 4),
            "monotone_constraints": dict(zip(FEATURE_KEYS, MONOTONE_CONSTRAINTS)),
            "num_boost_round": 300,
        },
        "fhs_reference": {
            "type": "Deterministic 6-subscore FHS (the decider / interpretable face)",
            "auc": round(auc_fhs, 4),
        },
        "agreement": agreement,
        "information_value_ranking": iv_rows,
        "n_train": len(tr),
        "n_test": len(te),
        "base_default_rate": round(float(y.mean()), 4),
        "split_seed": args.seed,
        "notes": [
            "Champion and challenger train on RAW engineered features; WOE bin cut-points "
            "are LEARNED from the cohort default rate (they replace the hand-set scoring ramps).",
            "Both models are monotone by construction (WOE merged to monotone; LightGBM "
            "monotone_constraints) — a regulator-deployable property a black box lacks.",
            "Champion coefficients are sign-constrained (all <= 0, since WOE is risk-aligned), "
            "so the scorecard never encodes 'higher WOE -> riskier'; collinear features shrink "
            "toward zero rather than flipping sign.",
            "Operating points (approve thresholds) aligned to the incumbent FHS approval rate "
            "so agreement compares which applicants are approved, not merely how many.",
            "Champion DECIDES (readable, RBI-explainable); challenger ADVISES (cross-check). "
            "FHS remains the interpretable face and the deterministic decider of record.",
            "IV = Information Value: higher = stronger good/bad separation (feature ranking).",
        ],
    }
    (ARTIFACTS / "model_card.json").write_text(json.dumps(model_card, indent=2), encoding="utf-8")

    # ---- Human summary ----
    print("=" * 70)
    print("HYBRID MODELS TRAINED  (champion + challenger)")
    print("=" * 70)
    print(f"  held-out n={len(te)}  train n={len(tr)}  base default {y.mean():.1%}")
    print()
    print(f"  AUC  champion (WOE+logit) : {auc_champ:.4f}")
    print(f"  AUC  challenger (mono GBM): {auc_chal:.4f}")
    print(f"  AUC  FHS (reference)      : {auc_fhs:.4f}")
    print()
    print("  Agreement (approve vs not, on held-out):")
    for kk, vv in agreement.items():
        print(f"    {kk:28s} {vv:.1%}" if "corr" not in kk else f"    {kk:28s} {vv:.3f}")
    print(f"\n  (sign-constrained logistic: all {k} WOE coefs <= 0; "
          f"{n_clamped} collinear feature(s) shrunk to ~0 by the constraint)")
    print()
    print("  Information Value ranking (top features, learned):")
    for r in iv_rows[:8]:
        print(f"    {r['label']:30s} IV={r['iv']:.3f}  bins={r['n_bins']}  mono={r['monotone']}")
    print()
    print(f"  Artifacts -> {ARTIFACTS/'champion.json'}")
    print(f"            -> {ARTIFACTS/'challenger.txt'}")
    print(f"            -> {ARTIFACTS/'model_card.json'}")


def _fit_sign_constrained_logit(W: np.ndarray, y: np.ndarray, C: float):
    """L2-penalised logistic regression with all feature coefficients constrained <= 0.

    WOE is risk-aligned so a deployable scorecard needs every coef non-positive. We
    minimise  NLL + (1/C)*||beta||^2 / (2n)  over [intercept, beta] with box bounds
    beta_j in [-inf, 0] (intercept free), via L-BFGS-B (scipy). Returns
    (n_shrunk_to_zero, intercept, coefs). Deterministic: warm-started from the
    unconstrained sklearn fit, no RNG."""
    from scipy.optimize import minimize

    n, kk = W.shape
    lam = 1.0 / (C * n) if C > 0 else 0.0

    # Warm start from the unconstrained fit (then project negatives).
    base = LogisticRegression(max_iter=5000, C=C, penalty="l2").fit(W, y)
    b0 = float(base.intercept_[0])
    beta0 = np.minimum(base.coef_[0].astype(float), 0.0)
    x0 = np.concatenate([[b0], beta0])

    yv = y.astype(float)

    def nll_and_grad(x):
        b, beta = x[0], x[1:]
        z = b + W @ beta
        # stable log-sigmoid
        p = np.where(z >= 0, 1.0 / (1.0 + np.exp(-z)), np.exp(z) / (1.0 + np.exp(z)))
        eps = 1e-12
        nll = -np.sum(yv * np.log(p + eps) + (1 - yv) * np.log(1 - p + eps))
        nll += lam * np.sum(beta ** 2)
        resid = p - yv
        gb = np.sum(resid)
        gbeta = W.T @ resid + 2.0 * lam * beta
        return nll, np.concatenate([[gb], gbeta])

    bounds = [(None, None)] + [(None, 0.0)] * kk   # intercept free; coefs <= 0
    res = minimize(nll_and_grad, x0, jac=True, method="L-BFGS-B", bounds=bounds,
                   options={"maxiter": 10000, "ftol": 1e-12, "gtol": 1e-9})
    intercept = float(res.x[0])
    coefs = res.x[1:].astype(float)
    coefs[coefs > 0] = 0.0                          # numerical safety
    n_shrunk = int(np.sum(np.abs(coefs) < 1e-6))    # features the constraint zeroed
    return n_shrunk, intercept, coefs


def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average-rank (Spearman helper) without scipy."""
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average ties
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    sums = np.zeros(len(counts))
    np.add.at(sums, inv, ranks)
    return (sums / counts)[inv]


if __name__ == "__main__":
    main()
