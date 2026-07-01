"""Pre-compute the hybrid models' per-persona output OFFLINE -> bake into persona JSON.

The model analogue of pregenerate_narration.py. The champion serves cheaply from
champion.json (pure numpy), but the CHALLENGER needs lightgbm + shap to run — which
the deployed container must not carry. So, exactly like the narration, we compute
each persona's challenger PD + SHAP attributions ONCE here (dev/offline, with the ML
deps) and freeze them into the persona file. The serve path then reads frozen text
and makes ZERO live model calls.

Each persona file gains a top-level "model_explain" block:
  {
    "champion":   { pd, score_points, approve, threshold, contributions[], model_version },
    "challenger": { pd, base_value, approve, threshold, contributions[](SHAP), model_version },
    "cross_check":{ fhs_approve, champion_approve, challenger_approve, agree, note },
    "generated_for_scorecard": "1.3.0"
  }
The champion block is recomputed live at serve time too (cheap, deterministic) and
the frozen copy is just a fallback; the challenger block is authoritative-frozen.

Usage (dev only):  python scripts/pregenerate_model_explain.py
Requires:          pip install lightgbm shap    (NOT in the deployed image)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sehat.challenger import cross_check
from sehat.champion import load as load_champion
from sehat.config import SCORECARD_VERSION
from sehat.engine import assess
from sehat.model_features import FEATURE_DOMAIN, FEATURE_KEYS, FEATURE_LABEL, extract_vector
from sehat.schema import CanonicalRecord

PERSONA_DIR = Path(__file__).resolve().parent.parent / "personas"
ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
TIMESTAMP = "2026-06-29T00:00:00Z"   # fixed: engine never calls Date.now()
CHALLENGER_PATH = ARTIFACTS / "challenger.txt"
MODEL_CARD_PATH = ARTIFACTS / "model_card.json"


def _challenger_threshold() -> float:
    mc = json.loads(MODEL_CARD_PATH.read_text(encoding="utf-8"))
    return float(mc["challenger"]["approve_threshold_pd"])


def _feature_row(f) -> np.ndarray:
    vec = extract_vector(f)
    return np.array([[vec[k] if vec[k] is not None else np.nan for k in FEATURE_KEYS]],
                    dtype=float)


def main() -> None:
    champion = load_champion()
    if champion is None:
        print("  ! artifacts/champion.json missing — run scripts/train_models.py first.")
        sys.exit(1)

    import lightgbm as lgb
    import shap

    booster = lgb.Booster(model_file=str(CHALLENGER_PATH))
    chal_thr = _challenger_threshold()
    explainer = shap.TreeExplainer(booster)

    for path in sorted(PERSONA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rec = CanonicalRecord.model_validate(data["record"] if "record" in data else data)
        assessment = assess(rec, timestamp=TIMESTAMP)
        f = assessment.features

        # --- Champion (recompute; also frozen as fallback) ---
        champ = champion.score(f)

        # --- Challenger: PD + SHAP on the raw feature row ---
        X = _feature_row(f)
        pd_raw = float(booster.predict(X)[0])

        # SHAP on the margin (log-odds): per-feature push on the raw margin, with
        # expected_value the base margin. Across shap versions a binary LightGBM
        # TreeExplainer returns either an ndarray or a 1-element list of ndarray;
        # normalise to the positive-class margin row. VERIFIED invariant (see
        # tests/test_models.py): base_margin + sum(contrib) == booster raw_score.
        sv = explainer.shap_values(X)
        if isinstance(sv, list):
            sv = sv[-1]                       # positive class
        contrib = np.asarray(sv)[0]
        base_margin = float(np.atleast_1d(explainer.expected_value)[-1])
        base_pd = 1.0 / (1.0 + np.exp(-base_margin))

        shap_contribs = []
        for i, key in enumerate(FEATURE_KEYS):
            val = X[0, i]
            shap_contribs.append({
                "key": key, "label": FEATURE_LABEL[key], "domain": FEATURE_DOMAIN[key],
                "value": (None if np.isnan(val) else round(float(val), 4)),
                "shap": round(float(contrib[i]), 4),
                "direction": "increases risk" if contrib[i] > 0 else "reduces risk",
            })
        shap_contribs.sort(key=lambda c: abs(c["shap"]), reverse=True)

        challenger_block = {
            "pd": round(pd_raw, 4),
            "base_value": round(base_pd, 4),
            "approve": bool(pd_raw <= chal_thr),
            "threshold": round(chal_thr, 4),
            "contributions": shap_contribs,
            "model_version": "challenger-mono-lgbm-1.0.0",
        }

        # --- Cross-check (the three independent views) ---
        fhs_approve = assessment.score.band in ("AA", "A")
        xc = cross_check(
            fhs_approve=fhs_approve,
            champion_approve=champ.approve,
            challenger_approve=challenger_block["approve"],
        )

        data["model_explain"] = {
            "champion": champ.to_dict(),
            "challenger": challenger_block,
            "cross_check": xc.to_dict(),
            "generated_for_scorecard": SCORECARD_VERSION,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        top_shap = shap_contribs[0]
        print(f"  {path.name:32s} champPD={champ.pd:.3f}({'Y' if champ.approve else 'N'}) "
              f"chalPD={pd_raw:.3f}({'Y' if challenger_block['approve'] else 'N'}) "
              f"agree={xc.agree}  topSHAP={top_shap['key']}")

    print(f"\nDone. Champion + challenger + SHAP frozen into persona JSON "
          f"(scorecard {SCORECARD_VERSION}). Demo path stays zero-live-model.")


if __name__ == "__main__":
    main()
