"""Explainability layer — render reason templates, optionally rephrase with Claude,
ALWAYS grounding-validate. (BUILD_STATUS task #9.)

The determinism principle (CLAUDE.md): the engine decides; Claude only narrates,
and only as a rephrasing of a canonical reason-code template, post-validated to
restate exactly what the engine produced. This module is where that boundary is
enforced. Three layers:

  1. render_reason(hit)      -> the deterministic template sentence (the backbone).
  2. narrate_reason(hit)     -> Claude rephrases the rendered sentence (OFFLINE).
  3. ground_narration(...)   -> asserts the rephrase introduced NO number absent
                                from the rendered template and did NOT flip a
                                RISK into a STRENGTH. On ANY failure -> fall back
                                to the template.

Key design choices (hardened by the Jun-29 audit):
  * Authorised numbers are extracted from the RENDERED TEMPLATE, not from the raw
    slot values. The rendered template is exactly what the customer sees on the
    deterministic card, so a hardcoded template number (e.g. the "20" in the
    EPFO-neutral note) and a comma/percent-formatted slot are BOTH authorised
    automatically, with no per-slot formatting logic.
  * The grounding validator is pure (regex + arithmetic). It runs on the DEMO
    PATH too — `explain_assessment` re-grounds every cached narration against the
    live computed values, so a stale or tampered narration silently falls back to
    the template. The deployed app makes ZERO live LLM calls.
  * `narrate_reason` is only ever called by the offline pre-generation script
    (scripts/pregenerate_narration.py). Nothing on the request path imports an
    LLM client.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Optional

from sehat.config import NARRATION_MODEL_ID, NARRATION_PROMPT_VERSION
from sehat.prompts import get_prompt
from sehat.reason_codes import Polarity, get as get_reason, render
from sehat.scoring import ReasonHit

# ---------------------------------------------------------------------------
# Number grounding.
# ---------------------------------------------------------------------------
# Matches integers/decimals with optional sign and thousands separators:
#   245,000   0.23   -14.0   22   1.5
_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
# Tolerance for float comparison. A faithful rephrase keeps the exact digits, so
# only trailing-zero / formatting noise needs to be absorbed; keep it tight so two
# genuinely distinct authorised numbers are never conflated.
_NUM_TOL = 1e-6


def _extract_numbers(text: str) -> list[float]:
    """Return the ABSOLUTE numeric magnitudes in `text` (commas stripped).

    We compare on absolute value so that (a) date components like "2026-08-31"
    (where the regex would otherwise read the separators as signs → 2026, -8, -31)
    and (b) a negative slope rendered "-14.8%" but faithfully rephrased "fell 14.8%"
    both MATCH. A faithful rephrase keeps the digit sequence; sign/format is noise.
    The hard guarantee (a digit-string absent from the template cannot appear in the
    narration) is unaffected.
    """
    out: list[float] = []
    for m in _NUMBER_RE.findall(text):
        token = m.replace(",", "").lstrip("+-")
        if not token or token == ".":
            continue
        try:
            out.append(abs(float(token)))
        except ValueError:  # pragma: no cover - regex guarantees parseable tokens
            continue
    return out


def _is_authorised(value: float, authorised: list[float]) -> bool:
    for a in authorised:
        if a == 0.0:
            # Exact match for zero — no relative band, so a tiny spurious value
            # (e.g. 5e-7) can't pass as "a reformatting of 0".
            if abs(value) <= 1e-9:
                return True
        elif abs(value - a) <= max(_NUM_TOL, abs(a) * 1e-4):
            return True
    return False


# Sentiment cues for the polarity-flip guard. This is a SECONDARY check — the
# number-grounding above is the hard guarantee, and the fallback is always the
# (correct) template, so a conservative heuristic here is safe: at worst it shows
# the template instead of a faithful rephrase.
_POSITIVE_CUES = {
    "strong", "steady", "consistent", "healthy", "comfortable", "diversified",
    "diverse", "robust", "good", "established", "active", "clear", "clean",
    "on-time", "ontime", "well", "buffer", "growing", "grew", "grows", "grow",
    "up", "rose", "rising", "rise", "improve", "improving", "improved", "increase",
    "increasing", "increased", "momentum", "positive", "solid", "aligns", "aligned",
    "reliable", "stable",
}
_NEGATIVE_CUES = {
    "volatile", "volatility", "thin", "short", "declining", "decline", "declined",
    "down", "fell", "falling", "fall", "drop", "dropped", "shrinking", "shrank",
    "late", "tight", "limited", "concentration", "concentrated", "risk", "risky",
    "negative", "overdrawn", "bounced", "bounce", "returned", "only", "consume",
    "consumes", "consuming", "weak", "insufficient", "missing", "spike",
    "exceeds", "integrity", "possible", "suspicious", "wash", "round-tripping",
}


def _cue_words(text: str) -> tuple[set[str], set[str]]:
    """Return (positive cues, negative cues) present in `text`."""
    words = set(re.findall(r"[a-z]+(?:-[a-z]+)?", text.lower()))
    return words & _POSITIVE_CUES, words & _NEGATIVE_CUES


@dataclass
class GroundingResult:
    grounded: bool
    reason: str                      # "" if grounded, else why it failed
    unauthorised_numbers: list[float]


def ground_narration(hit: ReasonHit, narration: str) -> GroundingResult:
    """Validate a rephrased `narration` against the deterministic template for `hit`.

    Passes iff (a) every number in the narration appears in the rendered template,
    and (b) the narration does not read as the opposite polarity. Pure function —
    no LLM, safe to run on the request path.
    """
    rc = get_reason(hit.code)
    template = render(hit.code, hit.values)

    authorised = _extract_numbers(template)
    for n in _extract_numbers(narration):
        if not _is_authorised(n, authorised):
            return GroundingResult(False, f"unauthorised number {n}", [n])

    # Polarity guard (secondary; the template is the safe fallback). The rule is
    # CUE-INTRODUCTION, not net-lean: a faithful rephrase may keep the template's own
    # sentiment words but must NOT INTRODUCE an opposite-polarity cue the template
    # didn't have. This catches the subtle cases net-lean misses:
    #   * mixed sentiment — a RISK rephrased "strong momentum despite volatility"
    #     introduces "strong/momentum" (positive) absent from the risk template;
    #   * sign inversion — a declining-turnover RISK rephrased "grew/up" introduces a
    #     positive cue absent from the template.
    # It does NOT false-flag the STRENGTH "No bounced payments" → "no bounces", because
    # "bounce(d)" is already in the template (introduced = {} ).
    t_pos, t_neg = _cue_words(template)
    n_pos, n_neg = _cue_words(narration)
    if rc.polarity == Polarity.RISK and (n_pos - t_pos):
        return GroundingResult(False,
                               f"risk narration introduces positive cue(s) {sorted(n_pos - t_pos)}", [])
    if rc.polarity == Polarity.STRENGTH and (n_neg - t_neg):
        return GroundingResult(False,
                               f"strength narration introduces negative cue(s) {sorted(n_neg - t_neg)}", [])

    return GroundingResult(True, "", [])


# ---------------------------------------------------------------------------
# Per-reason rendering / narration.
# ---------------------------------------------------------------------------
@dataclass
class ExplainedReason:
    code: str
    domain: str
    polarity: str
    template: str            # the deterministic rendered sentence (always present)
    narration: str           # validated rephrase, or == template on fallback
    grounded: bool           # narration passed grounding against live values
    used_llm: bool           # an LLM rephrase was applied (vs pure template)

    def to_dict(self) -> dict:
        return asdict(self)


def render_reason(hit: ReasonHit) -> str:
    """The deterministic backbone: the canonical template filled with slot values."""
    return render(hit.code, hit.values)


def explain_reason(hit: ReasonHit, narration: Optional[str] = None) -> ExplainedReason:
    """Build an ExplainedReason. If `narration` is provided (pre-generated), it is
    GROUNDED against the live values and used only if it passes; otherwise the
    deterministic template is used. No LLM is called here."""
    rc = get_reason(hit.code)
    template = render_reason(hit)
    if narration is not None and narration.strip() and narration.strip() != template:
        gr = ground_narration(hit, narration)
        if gr.grounded:
            return ExplainedReason(hit.code, rc.domain, rc.polarity.value,
                                   template, narration.strip(), True, True)
    # Fallback (or no narration supplied): the template IS the narration.
    return ExplainedReason(hit.code, rc.domain, rc.polarity.value,
                           template, template, True, False)


# ---------------------------------------------------------------------------
# Offline narration generation (LLM) — called ONLY by the pre-gen script.
# ---------------------------------------------------------------------------
def narrate_reason(hit: ReasonHit, client, *, model_id: str = NARRATION_MODEL_ID,
                   prompt_version: str = NARRATION_PROMPT_VERSION,
                   max_tokens: int = 160) -> ExplainedReason:
    """Render the template, ask Claude to rephrase it, GROUND the result, and fall
    back to the template on any failure or API error. OFFLINE only — `client` is an
    Anthropic client constructed by the pre-generation script with an API key. The
    deployed app never reaches this function.
    """
    rc = get_reason(hit.code)
    template = render_reason(hit)
    prompt = get_prompt(prompt_version).format(rendered=template)

    try:
        resp = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()
    except Exception as exc:  # noqa: BLE001 - any API failure -> safe template fallback
        return ExplainedReason(hit.code, rc.domain, rc.polarity.value,
                               template, template, True, False)

    if not text or text == template:
        return ExplainedReason(hit.code, rc.domain, rc.polarity.value,
                               template, template, True, False)

    gr = ground_narration(hit, text)
    if not gr.grounded:
        return ExplainedReason(hit.code, rc.domain, rc.polarity.value,
                               template, template, True, False)
    return ExplainedReason(hit.code, rc.domain, rc.polarity.value,
                           template, text, True, True)


# ---------------------------------------------------------------------------
# Decision narrative — deterministic "why this decision", built from gate codes.
# ---------------------------------------------------------------------------
# Maps the machine `blocking_gate` name to a plain-English clause. Not free text —
# a fixed lookup, so the rationale is as auditable as the score.
_GATE_CLAUSE = {
    "consent": "a valid data-sharing consent could not be confirmed",
    "bureau": "the borrower's credit-bureau record carries an adverse marker "
              "(e.g. SMA / write-off / willful-default) that policy treats as a hard stop",
    "sufficiency": "the available data was insufficient to score confidently",
    "fraud": "the data showed integrity / anti-gaming flags",
}


def decision_summary(*, decision: str, band: str, fhs: float,
                     blocking_gate: Optional[str]) -> str:
    """One deterministic sentence explaining the outcome. Numbers come straight
    from the engine; phrasing is a fixed template, never LLM-authored."""
    if decision == "approve":
        return (f"Approved on a Financial Health Score of {fhs:g} (band {band}) — "
                f"alternate-data fundamentals meet the approval policy; the limit "
                f"shown is indicative, subject to KYC, credit policy and KFS.")
    if decision == "decline":
        if blocking_gate and blocking_gate in _GATE_CLAUSE:
            return (f"Declined regardless of the Financial Health Score because "
                    f"{_GATE_CLAUSE[blocking_gate]}.")
        return (f"Declined — the Financial Health Score of {fhs:g} (band {band}) is "
                f"below the approval threshold on policy.")
    # refer
    if blocking_gate and blocking_gate in _GATE_CLAUSE:
        return (f"Referred for manual review because {_GATE_CLAUSE[blocking_gate]}.")
    return (f"Referred for manual review — a Financial Health Score of {fhs:g} "
            f"(band {band}) is a conditional/borderline outcome under policy.")


# ---------------------------------------------------------------------------
# Assessment-level explanation — what the API / UI consumes.
# ---------------------------------------------------------------------------
@dataclass
class Explanation:
    entity_id: str
    fhs: float
    band: str
    decision: str
    blocking_gate: Optional[str]
    indicative_limit: float
    post_loan_dscr: Optional[float]
    decision_summary: str
    strengths: list[dict]
    risks: list[dict]
    notes: list[dict]          # NEUTRAL reasons (coverage, EPFO-neutral, debt-unverified)
    gates: list[dict]          # GATE reasons (consent/bureau/fraud/sufficiency)
    narration_model_id: str
    narration_prompt_version: str
    narration_source: str      # "template" | "pregenerated"
    # The hybrid models' cross-check (champion WOE scorecard + challenger monotone GBM
    # + the deterministic FHS). None when models haven't been trained/frozen yet — the
    # card simply omits the cross-check section. NEVER decides anything: the FHS remains
    # the decider; these are validated second opinions surfaced for governance.
    model_cross_check: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _ground_champion(assessment) -> Optional[dict]:
    """Recompute the champion live from the frozen champion.json (cheap, pure numpy).

    The champion is deterministic at inference, so we recompute it on the request path
    (re-grounding it against the live features) instead of trusting a frozen copy —
    mirroring how narration is re-grounded. Returns None if the model isn't trained."""
    try:
        from sehat.champion import load as _load_champion
        champ = _load_champion()
        if champ is None:
            return None
        return champ.score(assessment.features).to_dict()
    except Exception:  # noqa: BLE001 - the cross-check is an enhancement, never fatal
        return None


def build_model_cross_check(assessment, model_explain: Optional[dict]) -> Optional[dict]:
    """Assemble the champion/challenger/FHS cross-check payload for the card.

    `model_explain` is the frozen block from the persona JSON (champion + challenger +
    SHAP), authored offline by pregenerate_model_explain.py. The CHAMPION is recomputed
    live (deterministic); the CHALLENGER is read from the frozen block (its lightgbm/shap
    deps are dev-only). The FHS approve signal is read live off the assessment. All three
    are recombined here so the agreement reflects the live decision.
    """
    from sehat.challenger import cross_check

    champion = _ground_champion(assessment)
    challenger = (model_explain or {}).get("challenger")
    if champion is None and challenger is None:
        return None

    fhs_approve = assessment.score.band in ("AA", "A")
    champ_appr = champion.get("approve") if champion else None
    chal_appr = challenger.get("approve") if challenger else None
    xc = cross_check(fhs_approve=fhs_approve, champion_approve=champ_appr,
                     challenger_approve=chal_appr)

    return {
        "champion": champion,
        "challenger": challenger,
        "cross_check": xc.to_dict(),
        "fhs_approve": fhs_approve,
    }


def explain_assessment(assessment, narration_cache: Optional[dict[str, str]] = None,
                       model_explain: Optional[dict] = None) -> Explanation:
    """Build the full, UI-ready explanation for an Assessment.

    `narration_cache` maps reason `code` -> a pre-generated rephrase (loaded from
    the frozen persona JSON). Every cached narration is RE-GROUNDED here against the
    live computed values; anything that fails silently falls back to its template.
    With no cache, every reason renders as its deterministic template. No LLM call.

    `model_explain` is the frozen champion/challenger/SHAP block from the persona JSON;
    when present, the card gains a model cross-check section. The champion is recomputed
    live; only the challenger's PD+SHAP are read frozen (dev-only deps). No model call.
    """
    cache = narration_cache or {}

    def build(hit: ReasonHit) -> ExplainedReason:
        return explain_reason(hit, cache.get(hit.code))

    score = assessment.score
    # Strengths / risks come from the (post-cap) score reasons.
    strengths = [build(h).to_dict() for h in assessment.strengths]
    risks = [build(h).to_dict() for h in assessment.risks]
    notes = [build(h).to_dict() for h in score.reasons if h.polarity == Polarity.NEUTRAL]
    gates = [build(h).to_dict() for h in assessment.outcome.gate_reasons]

    dec = assessment.decision
    sizing = dec.sizing
    summary = decision_summary(
        decision=dec.decision.value, band=score.band, fhs=score.fhs,
        blocking_gate=dec.blocking_gate,
    )

    return Explanation(
        entity_id=assessment.entity_id,
        fhs=score.fhs,
        band=score.band,
        decision=dec.decision.value,
        blocking_gate=dec.blocking_gate,
        indicative_limit=sizing.indicative_limit if sizing else 0.0,
        post_loan_dscr=sizing.post_loan_dscr if sizing else None,
        decision_summary=summary,
        strengths=strengths,
        risks=risks,
        notes=notes,
        gates=gates,
        narration_model_id=NARRATION_MODEL_ID,
        narration_prompt_version=NARRATION_PROMPT_VERSION,
        narration_source="pregenerated" if cache else "template",
        model_cross_check=build_model_cross_check(assessment, model_explain),
    )
