"""Segmentation report — the unified score, CUT BY SEGMENT (read-only, additive).

The Jun-30 explainer asked for a "segmented breakdown that rolls up into one
unified score" (sector / state / vintage-band / constitution). Per the EXPLAINER
build-implication, this is DESCRIPTIVE, not a new scored sub-model: we do not touch
the weights, the fit, or any spine artifact. We simply re-score the SAME held-out
validation slice (same seed/split as fit_and_validate.py) and report band
distribution + bad-rate by segment — proof the one unified FHS discriminates
consistently across the book, not just in aggregate.

This script is SPINE-SAFE by construction: it only READS cohort.jsonl + the fitted
config weights, and writes ONLY artifacts/segmentation_report.json. It never calls
fit_and_validate or train_models and never writes a weight.

Run:  python scripts/segment_cohort.py
Writes -> artifacts/segmentation_report.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sehat.config import SUBSCORE_WEIGHTS
from sehat.features import compute_features
from sehat.scoring import band_for, score
from sehat.sources import MockSource

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
SUBSCORE_ORDER = ["cash_flow", "revenue_vitality", "banking_discipline",
                  "compliance", "leverage", "digital_footprint"]
# Match fit_and_validate.py EXACTLY so this cuts the same held-out slice the
# validation AUC is measured on (seed 7, 30% stratified test split).
SPLIT_SEED = 7
TEST_SIZE = 0.3
BANDS_ORDER = ["AA", "A", "B", "C", "D"]


def _vintage_band(months: int) -> str:
    if months < 12:
        return "<1yr"
    if months < 36:
        return "1-3yr"
    if months < 60:
        return "3-5yr"
    return "5yr+"


def _segment_stats(rows: list[dict]) -> dict:
    """Band distribution + bad-rate for a list of {band, default} rows."""
    n = len(rows)
    n_def = sum(r["default"] for r in rows)
    band_counts = {b: 0 for b in BANDS_ORDER}
    for r in rows:
        band_counts[r["band"]] = band_counts.get(r["band"], 0) + 1
    # Approve = band AA/A on FHS (pre-gate) — same convention as the spine slide.
    n_appr = sum(1 for r in rows if r["band"] in ("AA", "A"))
    return {
        "n": n,
        "n_defaults": n_def,
        "bad_rate": round(n_def / n, 4) if n else 0.0,
        "approve_rate": round(n_appr / n, 4) if n else 0.0,
        "band_counts": band_counts,
    }


def _by_dimension(rows: list[dict], key: str, min_n: int = 10) -> list[dict]:
    """Group rows by a segment key; suppress thin strata (<min_n) to avoid noise."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    out = []
    for seg, grp in groups.items():
        if len(grp) < min_n:
            continue
        stats = _segment_stats(grp)
        stats["segment"] = seg
        out.append(stats)
    # Most populous first; ties broken by segment name for stable output.
    out.sort(key=lambda s: (-s["n"], s["segment"]))
    return out


def main() -> None:
    cohort_path = ARTIFACTS / "cohort.jsonl"
    if not cohort_path.exists():
        print("  ! artifacts/cohort.jsonl missing — run scripts/generate_cohort.py first.")
        sys.exit(1)

    records = MockSource(cohort_path).all_records()

    # GUARD: the segmentation MUST describe the same cohort the validation spine was
    # frozen on, or the portfolio page shows two different n_test values side by side
    # (the Jul-1 audit bug: a --n 600 default cohort gave n_test=180 next to the spine's
    # 300). Cross-check the on-disk cohort size against the frozen validation report's
    # total (n_train + n_test) and refuse to emit a mismatched report.
    vr_path = ARTIFACTS / "validation_report.json"
    if vr_path.exists():
        vr = json.loads(vr_path.read_text(encoding="utf-8"))
        expected = int(vr.get("n_train", 0)) + int(vr.get("n_test", 0))
        if expected and len(records) != expected:
            print(f"  ! COHORT SIZE MISMATCH: cohort.jsonl has {len(records)} rows but the frozen "
                  f"validation spine was built on {expected} (n_train+n_test). Regenerate with "
                  f"`python scripts/generate_cohort.py --n {expected} --seed 42` before segmenting, "
                  f"or the portfolio page will show two different 'same slice' sizes.")
            sys.exit(1)

    # Score every labeled entity with the FITTED config weights (read-only).
    rows_all, y = [], []
    for rec in records:
        if rec.label is None:
            continue
        f = compute_features(rec.for_scoring())
        sr = score(f, SUBSCORE_WEIGHTS)
        rows_all.append({
            "band": sr.band,
            "default": 1 if rec.label.defaulted_12m else 0,
            "sector": rec.entity.sector,
            "state": rec.entity.state,
            "reg_type": rec.entity.reg_type.value,
            "vintage_band": _vintage_band(rec.entity.udyam_vintage_months),
        })
        y.append(1 if rec.label.defaulted_12m else 0)

    # Reproduce the validation held-out slice exactly.
    y = np.array(y, dtype=int)
    idx = np.arange(len(y))
    _, te = train_test_split(idx, test_size=TEST_SIZE, random_state=SPLIT_SEED, stratify=y)
    test_rows = [rows_all[i] for i in te]

    report = {
        "n_cohort": len(rows_all),
        "n_test": len(test_rows),
        "split_seed": SPLIT_SEED,
        "test_size": TEST_SIZE,
        "overall": _segment_stats(test_rows),
        "by_sector": _by_dimension(test_rows, "sector"),
        "by_state": _by_dimension(test_rows, "state"),
        "by_reg_type": _by_dimension(test_rows, "reg_type"),
        "by_vintage_band": _by_dimension(test_rows, "vintage_band"),
        "notes": [
            "Descriptive segmentation of the SAME held-out validation slice "
            f"(seed {SPLIT_SEED}, {int(TEST_SIZE*100)}% stratified test split) — "
            "one unified FHS, cut by segment. Not a new scored sub-model; weights "
            "and the validation spine are untouched.",
            "Strata with n<10 suppressed to avoid small-sample noise.",
            "Approve = band AA/A on FHS (pre-gate), matching the validation slide.",
        ],
    }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS / "segmentation_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human summary.
    o = report["overall"]
    print(f"Segmentation over held-out test slice (n={report['n_test']}): "
          f"overall bad-rate {o['bad_rate']:.1%}, approve-rate {o['approve_rate']:.1%}")
    for dim in ("by_sector", "by_state", "by_reg_type", "by_vintage_band"):
        print(f"\n  {dim} ({len(report[dim])} strata >= 10):")
        for s in report[dim][:6]:
            print(f"    {s['segment']:16s} n={s['n']:3d}  bad={s['bad_rate']:5.1%}  "
                  f"approve={s['approve_rate']:5.1%}")
    print(f"\n  Artifact -> {out_path}")


if __name__ == "__main__":
    main()
