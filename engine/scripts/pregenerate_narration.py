"""Pre-generate persona narration OFFLINE -> bake into the persona JSON.

This is the ONLY place an LLM is ever called. It runs once, during development,
on the frozen personas, and writes a `narration` block into each persona file so
the deployed app serves static text and makes ZERO live LLM calls (the demo-path
rule from the audit).

For every reason in each persona's assessment it renders the deterministic
template, asks Claude (claude-haiku-4-5) to rephrase it, then GROUNDS the result;
anything that fails grounding (or any API error, or a missing API key) falls back
to the template. The written narration is therefore always safe to ship.

Usage:
  ANTHROPIC_API_KEY=...  python scripts/pregenerate_narration.py
  python scripts/pregenerate_narration.py --no-llm     # template-only (offline)

The persona file gains a top-level "narration" object:
  {
    "model_id": "claude-haiku-4-5", "prompt_version": "narr-v1",
    "generated_for_scorecard": "1.3.0",
    "by_code": { "CF_INFLOW_CONSISTENT": "<rephrase>", ... }   # code -> text
  }
Only reasons whose narration PASSED grounding AND differs from the template are
stored (a missing code => the API falls back to the template at serve time).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sehat.config import NARRATION_MODEL_ID, NARRATION_PROMPT_VERSION, SCORECARD_VERSION
from sehat.engine import assess
from sehat.explain import explain_reason, narrate_reason
from sehat.schema import CanonicalRecord

PERSONA_DIR = Path(__file__).resolve().parent.parent / "personas"
TIMESTAMP = "2026-06-29T00:00:00Z"   # fixed: engine never calls Date.now()


def _all_hits(assessment) -> list:
    """Every ReasonHit we want narration for: score reasons + gate reasons."""
    seen, hits = set(), []
    for h in list(assessment.score.reasons) + list(assessment.outcome.gate_reasons):
        if h.code not in seen:
            seen.add(h.code)
            hits.append(h)
    return hits


def _make_client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        print("  ! anthropic SDK not installed; install with `pip install anthropic` "
              "or run with --no-llm. Falling back to templates.")
        return None
    return anthropic.Anthropic(api_key=key)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true",
                    help="skip Claude; write template text only (still grounding-clean)")
    args = ap.parse_args()

    client = None if args.no_llm else _make_client()
    if client is None and not args.no_llm:
        print("  ! No ANTHROPIC_API_KEY found — generating template-only narration "
              "(safe; the card simply shows the canonical sentences).")

    total_llm = total_fallback = 0
    for path in sorted(PERSONA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rec = CanonicalRecord.model_validate(data["record"] if "record" in data else data)
        assessment = assess(rec, timestamp=TIMESTAMP)

        by_code: dict[str, str] = {}
        n_llm = n_fb = 0
        for hit in _all_hits(assessment):
            if client is not None:
                er = narrate_reason(hit, client)
            else:
                er = explain_reason(hit, None)   # template only
            if er.used_llm and er.narration != er.template:
                by_code[hit.code] = er.narration
                n_llm += 1
            else:
                n_fb += 1

        data["narration"] = {
            "model_id": NARRATION_MODEL_ID if client is not None else "template-only",
            "prompt_version": NARRATION_PROMPT_VERSION,
            "generated_for_scorecard": SCORECARD_VERSION,
            "by_code": by_code,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        total_llm += n_llm
        total_fallback += n_fb
        print(f"  {path.name:32s} llm-rephrased={n_llm:2d}  template-fallback={n_fb:2d}")

    mode = "template-only" if client is None else f"{NARRATION_MODEL_ID} + grounding"
    print(f"\nDone ({mode}). Rephrased {total_llm}, fell back {total_fallback}. "
          f"Demo path stays zero-live-LLM — narration is now static in the persona JSON.")


if __name__ == "__main__":
    main()
