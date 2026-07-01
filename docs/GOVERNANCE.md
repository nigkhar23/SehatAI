# Governance & Compliance — Sehat

> Source document for **deck slide 12** (Additional Details / Future Development → governance).
> Everything here maps to code that exists in `engine/sehat/`. A bank cannot deploy a black box that
> gambles on credit; this is how Sehat is governable.

## 1. The non-negotiable principle

**The score and the credit decision are 100% deterministic, rule/stat-based, and auditable.** The LLM
(Claude) never decides anything — it only rephrases machine-generated reason-code *templates*, and even
then a **grounding validator** rejects any narration that introduces a number absent from the engine's
computation or flips a risk into a strength (`sehat/explain.py::ground_narration`), falling back to the
deterministic template. The deployed app makes **zero live LLM calls**: narration is pre-generated
offline and shipped as static text in the persona JSON.

## 2. Data-principal / data-fiduciary roles (DPDP Act, 2023)

- **Data Principal** — the MSME (and its proprietor). **Data Fiduciary** — the lender (IDBI).
- Sehat processes data **only** under a valid, unexpired, in-scope **consent artefact**
  (`ConsentArtefact`, ReBIT-style: `consent_id`, start/expiry, `fi_types`, purpose code/text, fetch type,
  `DataLife`). The consent gate (`pipeline.py::check_consent`) **refuses to score** without one, refuses
  on expiry, and refuses if the data held exceeds the consented FI-type scope (`CN_MISSING` / `CN_EXPIRED`
  / `CN_SCOPE_MISMATCH`).
- **Purpose limitation:** the only purpose is credit assessment (`purpose_code 101`); the engine does not
  repurpose the data.

## 3. Fetch-minimization, retention & erasure

- **Fetch-minimization:** only the FI types the consent grants are read; absence of a source is a
  first-class state (reweight, not zero), never an excuse to over-fetch.
- **Retention:** raw transaction lines / GST returns should be purged after the consent `DataLife`
  window. What is retained for governance is **derived, minimal, and non-PII**: the sub-scores, the
  reason *codes*, the FHS/band/decision, and content-addressed **hashes** of the input and the record.
- **Audit by hash, not by PII:** `audit.py::canonical_input_hash` stores a SHA-256 of the (label-stripped)
  input, so a bank can prove the inputs were unchanged **without storing the raw PII**.

## 4. The LLM PII boundary (data-residency-safe)

- The narration layer receives **only** an already-rendered reason-code template (e.g. *"83% of GST
  returns filed on or before the due date."*) — never counterparty names, narration text, account numbers,
  or raw GST line items.
- Narration is generated **offline**, on frozen personas, and the result is **grounding-validated** before
  it is ever shipped. At serve time the app re-grounds the cached narration against the live computed
  values; anything stale or tampered silently falls back to the template.
- The exact rephrase prompt is **version-controlled** (`sehat/prompts.py`, keyed by
  `NARRATION_PROMPT_VERSION`) and stamped into every audit record, so any narration is reproducible.

## 5. Immutable audit trail (RBI Digital Lending Guidelines)

Every assessment emits an `AuditRecord` (`audit.py`), appended to an append-only JSONL log
(`AuditLog`, wired into the live API path). Each record captures:

| Field | Why it matters |
|---|---|
| `timestamp`, `entity_id`, `consent_id` | who/when, under which consent |
| `scorecard_version` | exact constant set + weights in force (`config.SCORECARD_VERSION`) |
| `input_hash`, `record_hash` | tamper-evidence without storing PII |
| `subscores`, `effective_weights` | the full numeric basis of the score |
| `reason_codes`, `gate_reason_codes` | every signal surfaced |
| `fhs`, `band`, `decision`, **`blocking_gate`** | the outcome **and which gate forced it** |
| `indicative_limit`, `post_loan_dscr` | the sizing basis |
| `narration_model_id`, `narration_prompt_version` | LLM provenance (even though pre-generated) |

Records are **never mutated in place**; re-scoring under a re-fit scorecard produces a *new* record under
a new version. This is the trail an auditor, a regulator, or an appeal officer reads.

## 6. The hard-gate (necessary-but-insufficient credit hygiene)

A great alternate-data profile **does not override** adverse bureau hygiene. The bureau hard-gate
(`pipeline.py::check_bureau`) **declines regardless of FHS** on a live SMA, write-off, settlement, or
willful-default marker (demonstrated by persona **P5** — FHS 86/AA but a live SMA-2 → decline,
`blocking_gate = bureau`). A clean bureau does **not** auto-approve; it is necessary, not sufficient.

## 7. Fraud / anti-gaming controls

The fraud layer (`pipeline.py::check_fraud`) can **cap** a sub-score or **refer/veto**: round-tripping
(wash flows that net to ~zero), recency spikes, payer-concentration inflation, GST integrity (inflows
materially exceeding declared turnover), and declared-turnover-with-no-tax. Caps only ever *lower* a
score, preserving the monotonicity guarantee.

## 8. Fairness, drift & model risk

- **Monotonicity:** each sub-score is a weighted average of monotone ramps — perturbing one input *worse*
  never *raises* the score (by construction).
- **No protected-attribute features:** the engine scores financial behaviour, not demographics; sector and
  state feed only seasonality/limit context, never a penalty.
- **Drift monitoring (roadmap):** track PSI on the sub-score distributions and re-fit on a new cohort with
  a `SCORECARD_VERSION` bump; the validation report (`validation_report.json`) is the re-certification
  artefact. The fit is **idempotent** (shrinks toward a fixed design-intent prior), so a re-run on the
  same cohort reproduces the same weights — a clone-and-verify guarantee.

## 9. Human-in-the-loop & grievance

- **Refer** is a first-class outcome — borderline (band B) and soft-gate trips route to **manual review**,
  not an automated no.
- The decision summary and the full reason-code trail give a review/appeal officer a complete,
  plain-English basis for the decision (`explain.py::decision_summary` + the "Why this decision" drawer).
- Output is labelled **indicative eligibility**, subject to KYC, credit policy and KFS — the binding
  sanction is the bank's act, not the score's.

## 10. What is synthetic vs real (honest scope)

Round-1 metrics are computed on **synthetic data calibrated to RBI/MSME distributions, pending sandbox
validation**. The two-phase plan is explicit: R1 proves the *architecture* on synthetic data; Round 2
proves *discrimination* on real sandbox MSME data. No production credit decision should rely on R1 metrics.
