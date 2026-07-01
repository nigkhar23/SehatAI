# Deck content — fill the official IDBI Innovate 2026 PPT, slide by slide

> **How to use this file:** the official template (`assets/idbi-innovate-2026-template.pptx`) has 13 content
> slides + 2 branding slides. Copy each block below into the matching slide, keep the template's headings/layout,
> then **export to PDF** and submit. All numbers here are pulled live from the engine artifacts (Jun 30, 2026) —
> they match the deployed site and the repo. Don't paraphrase the metrics; they're exact.
>
> **Live links (already deployed):**
> - Product (Vercel): **https://sehat-ai-84ja.vercel.app/**
> - GitHub: **https://github.com/nigkhar23/SehatAI**
> - Demo video: _record + paste link (see DEMO_SCRIPT below)_
>
> **Speaker notes** are marked _SN:_ — put them in the slide's notes pane, not on the slide.

---

## Slide 1 — Team Details

- **Team name:** SehatAI
- **Team leader:** Prakhar
- **Problem Statement:** Track 03 — AI/ML-driven MSME Financial Health Card (Financial Inclusion / Digital Lending / Credit Decisioning)
- **Submission:** Live product + public GitHub repo + this deck

_SN: Solo entry (allowed, 1–4 members). One human + an AI build partner. Entered Track 03 deliberately — it's the track where deployability, not just accuracy, wins._

---

## Slide 2 — Brief about the idea

**Sehat ("health") is an AI/ML-driven Financial Health Card that lends to credit-invisible MSMEs a bureau would reject — and shows its work.**

Millions of small businesses (kirana stores, small manufacturers) have never taken a formal loan, so they have **no bureau/CIBIL history**. Conventional underwriting sees nothing and declines them — even when the business is healthy and earning.

Sehat scores them on **alternate data they already generate** — GST returns, UPI payments, bank-account (Account Aggregator) cash-flow, EPFO, and — for the thinnest files — **operational proxies like electricity consumption** — producing a 0–100 **Financial Health Score**, an **approve / refer / decline** decision with an indicative limit, and a **plain-English, fully auditable explanation**.

_SN: One line — "the bureau can't see this business, but its bank account, tax filings, and even its electricity meter tell a clear story, and that story says it's a safe bet." The operational-proxy angle is the exact thing the Track-03 owner asked for on Jun 30._

---

## Slide 3 — Opportunities · How it's different · How it solves · USP

**The opportunity**
- ~64 million MSMEs in India; a large share are **credit-invisible** (new-to-credit / thin-file). Bureau-only scorecards structurally **cannot price** them → blanket decline → a financial-inclusion gap *and* an unserved lending book for the bank.

**How it's different**
- The score and decision are **100% deterministic, rule/stat-based, and auditable.** The LLM (Claude) **never decides** — it only rephrases machine-generated reason codes, and a grounding validator blocks it from inventing a number or flipping a risk into a strength.

**How it solves it**
- Aggregates alternate data → **6 explainable sub-scores** → a Financial Health Score → an indicative credit decision, wrapped in a **bureau hard-gate + fraud layer + consent + audit trail**.

**USP (the one line)**
- *"Explainable **AND** it empirically separates good from bad (AUC/KS validated) **AND** a bank can actually govern it."* Most teams will claim "explainable." Few can show validated discrimination **and** bank-grade governance on the same system.

_SN: "Explainable" is table-stakes — 5+ teams will say it. Our moat is the combination: a validated Credit-Invisible Lift, behind a bureau hard-gate and a fraud layer, with a full audit trail._

---

## Slide 4 — List of features

**Scoring & ML**
- **6 explainable sub-scores** (Cash-Flow, Revenue, Banking Discipline, Compliance, Leverage, Digital Footprint) → weighted **Financial Health Score**; weights are **fitted by logistic regression** on a labelled cohort, not guessed.
- **Operational proxies for the thinnest files** — electricity / water / fuel meters. Steady consumption confirms a business is genuinely operating at capacity even when its GST/UPI file is too thin to price; a sharp drop flags a slowdown. *(The exact alternate-data source the Track-03 owner named on Jun 30.)*
- **Hybrid champion/challenger models** (the "AI/ML-driven" core): a learned **WOE + logistic scorecard** (champion, decides & explains) cross-checked by a **monotonic gradient-boosting model + SHAP** (challenger, advises). 94% agreement; both monotone by construction.

**Risk controls & governance**
- **Bureau hygiene hard-gate** (SMA / write-off / willful-default → decline regardless of score).
- **Fraud / anti-gaming layer** (round-tripping, recency spikes, payer concentration, GST integrity — can cap or veto).
- **Data-sufficiency gate** + data-coverage meter; missing data **reweights, never penalises**.
- **Reason-code explainability** — template backbone + LLM rephrase, **grounding-validated**.
- **Immutable audit record** (input hash, scorecard version, model + prompt version) + scorecard versioning.

**Decisioning & integration**
- **Indicative limit sizing** to keep **post-loan DSCR ≥ 1.3–1.5**, with volatility & concentration haircuts.
- **Risk-qualified Credit-Invisible Lift**; portfolio / bank-side view.
- **Consent artefact** (ReBIT/AA); **ULI** as data-in rail, **OCEN** as offer-out — Round-2 integration points.

---

## Slide 5 — Process flow / Use-case

**Assembly line (every stage is deterministic and logged):**

1. **Consent check** — valid, unexpired AA/ReBIT consent, or refuse to score.
2. **Data-sufficiency gate** — ≥6 months txns, ≥2 GST returns, else refer.
3. **Fraud / anti-gaming layer** — detect & cap gamed inflows.
4. **Bureau hard-gate** — adverse marker → decline regardless of health.
5. **Feature engine** → **Scoring engine** (6 sub-scores → FHS + reason codes).
6. **Champion + challenger cross-check** (validated second opinions).
7. **Decision layer** — approve / refer / decline + indicative limit.
8. **Explainability** (grounded narration) → **Immutable audit record** → **Health Card UI**.

_SN: Primary user is the bank's credit officer; the MSME receives the explained outcome and can request a review. Walk the P5 example: great financials, but a live SMA on the proprietor → the bureau gate correctly declines. Necessary-but-insufficient._

---

## Slide 6 — Wireframes / Mock diagrams (optional)

Use live screenshots (see Slide 10) — the deployed Health Card is the wireframe:
- **Health Card:** FHS gauge + band, 6 sub-score radar, strengths/risks with reason-code badges, data-coverage meter, gate strip, **model cross-check** (champion vs challenger vs score), "Why this decision" audit drawer.
- **Portfolio view:** book-level decision counts, indicative exposure, cohort band stats.
- **Validation page:** AUC/KS, bad-rate-by-band, Credit-Invisible Lift, Information-Value feature ranking.

---

## Slide 7 — Architecture diagram

```
Data sources (GST / AA bank txns / UPI / EPFO / operational proxies)  [ULI = RBI data-pull rail IN — R2]
        │
        ▼   DataSource adapter  ── MockSource (R1)  |  SandboxSource (R2)   ← the swap point
        ▼   Canonical Pydantic schema  (every layer below reads ONLY this)
        │
   PRE-SCORE PIPELINE (each can cap/veto):  Consent → Sufficiency → Fraud → Bureau hard-gate
        │
        ▼   Feature engine (pandas)
        ▼   Scoring engine — 6 sub-scores → FHS + reason codes  (weights fit by logistic regression)
        │        ‖ Champion (WOE+logistic) + Challenger (monotonic GBM + SHAP) — validated cross-check
        ▼   Decision layer — approve/refer/decline + indicative limit (post-loan DSCR ≥ 1.3–1.5)
        │        ‖ Explainability — reason-code templates + LLM rephrase, grounding-validated
        ▼   Immutable audit record (input hash · scorecard version · model + prompt version)
        ▼   Health Card UI + Portfolio view          [OCEN = offer-out rail to LSPs — Round 2]

  Behind it all: a 1,000-entity LABELLED COHORT → held-out AUC / KS / Gini + bad-rate AA→D + Credit-Invisible Lift.
```

- **R1 deploy:** Next.js (static export) on **Vercel** + FastAPI **Docker** engine (Render). **R2:** same Docker image → **AWS** App Runner / ECS.
- **The swap point is the whole R1→R2 trick:** both sources map raw shapes into one canonical schema, so a sandbox surprise is contained in one mapping function.

---

## Slide 8 — Technologies

- **Engine:** Python · FastAPI · pandas / numpy · **scikit-learn** (logistic weight fit + WOE champion) · **LightGBM** (monotonic challenger) · **SHAP** (per-applicant attribution) · Pydantic (canonical schema).
- **Determinism boundary:** model training & SHAP run **offline**; the deployed container serves **frozen** outputs via pure numpy — **zero live model/LLM calls** on the demo path.
- **Explainability LLM:** Claude (`claude-haiku-4-5`) — **narration only**, pre-generated offline, grounding-validated.
- **Frontend:** Next.js 14 · React · Tailwind · Recharts · static export.
- **Deploy:** Vercel (web) + Docker/Render (engine) for Round 1; **AWS** (App Runner/ECS) for Round 2 — same image.

_SN: lightgbm/shap/scipy are dev-only — the deployed container imports none of them. That's deliberate: deterministic, lean, reproducible at inference._

---

## Slide 9 — Estimated implementation cost (optional)

- **Per-assessment cost ≈ near-zero:** scoring is deterministic numpy/pandas; **no live LLM or model call** at serve time (narration + challenger outputs are pre-computed and frozen).
- **LLM cost:** one-time offline narration generation only (short text, cached) — effectively $0 per live assessment.
- **Infra (R1):** Vercel free tier (static) + a small container instance — single-digit $/month.
- **Scales sub-linearly:** marginal cost per additional applicant is a few milliseconds of CPU. Orders of magnitude cheaper than manual underwriting of a thin-file MSME.

---

## Slide 10 — Snapshots of the prototype

Screenshots from the live app (**https://sehat-ai-84ja.vercel.app/**). Recommended captures:

1. **P2 — Thin-file hero** (`/card/P2_HERO`): FHS **78.1 / Band A / approve ₹13.0L**. The winning case — bureau can't price it, Sehat approves with reasons. Cross-check: **all 3 models agree**.
2. **P7 — Operational-proxy manufacturer** (`/card/P7_PROXY_MFG`): FHS **72.0 / Band A / approve ₹17.75L**. **Genuinely credit-invisible** — no bureau file at all, thin GST, no UPI — so a conventional scorecard cannot price it. Its **electricity meter is steady**, and that tips the score across the approve line. Show the **electricity sparkline panel**: *this is the exact operational-proxy source the Track-03 owner asked for on Jun 30, in-product.* **Then toggle to P7B** (`/card/P7B_PROXY_SLOWDOWN`) — the *same business* a quarter later with **electricity crashed**: the same meter now fires `RV_PROXY_TREND_BREAK` and the decision steps down to **refer (Band B)**. The proxy genuinely moves the decision, both ways. *(Honest note for Q&A: the proxy-blind champion still approves the slowdown case — so the deterministic score caught a downturn the bureau-style model can't see, and routed it to human review.)*
   - _SN (if asked why P7's ₹17.75L limit exceeds P2's ₹13.0L despite a thinner file): the limit tracks **verified monthly surplus**, not how much data exists. P7 has higher revenue (₹5.6L vs ₹4.2L/mo) and steadier inflows (lower CV → smaller volatility haircut), and the limit is sized so **post-loan DSCR stays ≤ 1.5** — it's surplus-driven and DSCR-capped, not a reward for a rich file._
3. **P5 — Thin-but-delinquent** (`/card/P5_DELINQUENT`): FHS **86.0** but **DECLINED** — live SMA-2 trips the bureau hard-gate. Shows the gate working.
4. **P6 — Partial-data + fraud** (`/card/P6_FRAUD_PARTIAL`): missing UPI/EPFO (graceful degradation) + round-tripping caught and capped.
5. **Model cross-check panel** (P3 — `/card/P3_BORDERLINE`): champion & challenger **disagree → routed to human review** (governance in action).
6. **"Why this decision" drawer:** machine reason codes + input/record hash + scorecard version.

**Demo persona table (live, exact):**

| Persona | FHS | Band | Decision | Note |
|---|---|---|---|---|
| Strong formal | 98.6 | AA | Approve ₹27.5L | clean baseline |
| **Thin-file hero** | 78.1 | A | **Approve ₹13.0L** | **the winning case** |
| **Operational-proxy mfr** | 72.0 | A | **Approve ₹17.75L** | **credit-invisible; steady electricity tips it to approve** |
| **↳ same mfr, slowdown** | 69.7 | B | **Refer** | **electricity crashed → trend-break → step down** |
| Volatile borderline | 65.3 | B | Refer | nuance; models disagree → review |
| Genuine decline | 24.9 | D | Decline | correct "no" |
| Thin-but-delinquent | 86.0 | AA | **Decline** | bureau hard-gate (SMA-2) overrides |
| Partial / fraud | 59.3 | B | Refer | fraud layer caps round-tripping |

---

## Slide 11 — Prototype Performance / Benchmarking  ★ THE SPINE SLIDE

**Held-out validation** — 1,000-entity labelled synthetic cohort, **700 train / 300 test**, base default rate 20.0%. A latent repayment propensity drives both the noisy features and the seeded default label, so the AUC is **honest, not circular**.

| Metric | Value |
|---|---|
| **AUC** | **0.7829** |
| Gini | 0.5658 |
| KS | 0.4583 |
| Bad-rate monotone AA→D | ✓ Yes |

**Bad rate by band** (monotonically decreasing risk): AA **2.3%** · A **6.2%** · B **23.7%** · C **47.9%** · D **50.0%**.

**★ Risk-qualified Credit-Invisible Lift** — on the thin/no-bureau-file "reject" cohort (n=88) a conventional scorecard cannot price:
- Sehat **approves 41%** (36 of 88) — **at a 5.6% bad rate** *(indicative: synthetic cohort, n=36 approved; Round-2 sandbox validates on real data).*
- The ones it **declines** default at **34.6%** (cohort baseline 22.7%).
- **+17.2 percentage-point** bad-rate reduction vs blanket-approving the cohort → **expands the book while holding losses under appetite.**

_SN: the lift ratios are the proof-of-method on a labelled synthetic cohort; the small approved-n (36) is why we caveat it as indicative and re-validate on the bank's real data in Round 2. Lead with the mechanism (safe expansion of a rejected book), not the decimal._

**Hybrid champion/challenger cross-check** (model-risk governance):
- Champion (WOE+logistic) AUC **0.745** · Challenger (monotonic GBM) AUC **0.773** · FHS reference AUC **0.783**.
- **Champion↔challenger agreement 94%**; PD rank-correlation **0.948**. Three independent models, same conclusion.
- **Information-Value feature ranking (learned, not guessed):** Liquidity runway 0.48 · DSCR proxy 0.48 · Bounce rate 0.41 · Days overdrawn 0.32 · UPI velocity 0.32.

_Caveat (state it honestly): on synthetic data calibrated to RBI/MSME distributions; pending sandbox validation in Round 2. The method is what's proven; Round 2 re-runs the same `.fit()` on the bank's real data._

---

## Slide 12 — Additional details / Future development

**Round 2 (sandbox, Jul 22–31):**
- Map real AA/GST/UPI sandbox payloads into the canonical schema (one mapping function — the swap point), wire `SandboxSource` as the async AA consent state-machine, prove 1–2 rails end-to-end, deploy one persona to a **real URL on AWS**.

**Governance & compliance (deployability is the moat):**
- **RBI Digital Lending** — every rejection gets a defensible reason (the reason codes).
- **DPDP / data-fiduciary** — consent artefacts, fetch-minimisation, retention/erasure, LLM PII boundary.
- **Human-in-the-loop** — bank-officer override-with-logging (name + reason + timestamp); MSME can request review/appeal. Champion/challenger disagreement auto-routes to review.
- Immutable audit trail + scorecard versioning + drift/PSI monitoring.

**Product roadmap:** portfolio analytics & early-warning; sector-risk calibration; OCEN offer-out to LSPs; pilot-cohort study with the bank.

---

## Slide 13 — Links

- **GitHub Public Repository:** https://github.com/nigkhar23/SehatAI
- **Demo Video Link (3 minutes):** _‹paste after recording — see DEMO_SCRIPT below›_
- **Final Product Link (deployment):** https://sehat-ai-84ja.vercel.app/

---

## Slides 14–15 — branding (image-only)
Leave exactly as the template ships. Do not edit.

---

# 3-minute demo video script (for the slide-13 link)

> Record screen on the live site (**https://sehat-ai-84ja.vercel.app/**). ~3 min. Calm, plain language.

- **0:00–0:25 — The problem.** "Millions of small businesses have no credit history, so banks reject them even when they're healthy. Sehat fixes that using the data they already generate — GST, UPI, bank cash-flow."
- **0:25–1:05 — The winning case (P2 hero).** Open `/card/P2_HERO`. "Thin file — a bureau can't price this. Sehat scores 78, Band A, approves ₹13 lakh — and here's *why*: steady inflows, healthy surplus, on-time GST, no bounces." Scroll to the **model cross-check**: "A learned scorecard and a stronger AI model both independently agree — high confidence."
- **1:05–1:30 — Operational proxies (P7 → P7B).** Open `/card/P7_PROXY_MFG`, scroll to the **electricity sparkline**. "This manufacturer has *no* bureau file, thin GST, no UPI — a conventional scorecard is blind to it. But its electricity meter is steady, which confirms it's genuinely running at capacity — and that tips Sehat to approve. This is the exact operational-proxy source your team named in the problem-statement session." Toggle to `/card/P7B_PROXY_SLOWDOWN`: "Same business, a quarter later — its electricity has fallen sharply. The same meter now flags a slowdown, and Sehat steps the decision down to refer. The proxy moves the decision, both ways."
- **1:25–1:55 — It says no correctly (P5 + P4).** Open `/card/P5_DELINQUENT`: "Financials look great — score 86 — but there's a live default marker on the proprietor, so the bureau hard-gate declines it. The score isn't blind." Mention P4 as a genuine weak-fundamentals decline.
- **1:55–2:35 — Proof it works (validation page).** "This isn't a guess. On held-out data: AUC 0.78, risk falls cleanly from band D to AA. On the rejected cohort, we safely approve 41% at a 5.6% bad rate versus 35% for the ones we decline — we expand the book without taking on bad risk."
- **2:35–3:00 — Why a bank can deploy it.** "The math decides; the AI only writes the explanation, and a validator stops it inventing anything. Every decision is logged and auditable. Explainable, validated, and governable — AI a bank is actually allowed to use." End on the GitHub + live URL.
