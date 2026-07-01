"""Generate the labeled synthetic cohort and freeze it to disk.

Run once (and re-run only when the generator changes). Writes:
  artifacts/cohort.jsonl   — one CanonicalRecord (with latent label) per line

The cohort is the validation spine's substrate. Personas are generated
separately by `generate_personas.py` and frozen into `personas/` so their inputs
are never tuned to fix a score.

Usage:
    python scripts/generate_cohort.py [--n 600] [--seed 42]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sehat.synth import generate_cohort

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "cohort.jsonl"

    records = generate_cohort(n=args.n, seed=args.seed)
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(rec.model_dump_json())
            fh.write("\n")

    dr = sum(1 for r in records if r.label and r.label.defaulted_12m) / len(records)
    print(f"Wrote {len(records)} records -> {out}")
    print(f"Seeded 12-month default rate: {dr:.1%}")


if __name__ == "__main__":
    main()
