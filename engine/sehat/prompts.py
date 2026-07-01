"""Versioned narration prompts — audit reproducibility for the LLM layer.

The determinism principle (CLAUDE.md) requires that a bank can reproduce exactly
what Claude was told when it rephrased a reason code. The prompt STRING therefore
lives in version control, keyed by the same id the audit record stamps
(`NARRATION_PROMPT_VERSION` in config.py). Bump the version here AND in config.py
together whenever the wording changes, and re-run the grounding validator over all
pre-generated narration to re-certify it.

These prompts never *decide* anything. They instruct Claude to perform a bounded
rephrase of an already-rendered, engine-produced template — same numbers, same
polarity, no new facts — which the grounding validator then independently checks.
"""

from __future__ import annotations

# narr-v1 — the rephrase contract. Deliberately strict: the model is told it is a
# compliance-bound rephraser, not an author. The grounding validator is the
# backstop; this prompt is the first line of defence.
NARRATION_PROMPT_V1 = """\
You are a compliance-bound rephraser for an Indian bank's MSME credit Health Card.
You are NOT a credit analyst and you NEVER make or imply a lending decision.

You will receive ONE sentence that a deterministic scoring engine already produced
(a "reason"). Rewrite it into one warm, plain-English sentence a small-business
owner can understand. Follow these rules exactly:

1. Keep every number EXACTLY as written — same digits, same units (₹, %, months,
   CV). Do not round, convert (e.g. no "lakh"/"crore"), recompute, or add any
   number that is not already in the sentence.
2. Never change the meaning's direction. A risk/weakness must stay a
   risk/weakness; a strength must stay a strength. Do not soften a risk into a
   positive or inflate a strength.
3. Add no new facts, causes, advice, or promises. Only restate what is given.
4. Output ONLY the rewritten sentence — no preamble, quotes, or notes.

Reason to rephrase:
{rendered}
"""

# Registry so audit ids resolve to the exact string used.
PROMPTS: dict[str, str] = {
    "narr-v1": NARRATION_PROMPT_V1,
}


def get_prompt(version: str) -> str:
    try:
        return PROMPTS[version]
    except KeyError as exc:  # pragma: no cover - guards against a config/prompt drift
        raise KeyError(
            f"Unknown narration prompt version {version!r}. "
            f"Register it in prompts.py (known: {sorted(PROMPTS)})."
        ) from exc
