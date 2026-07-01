# Build Plan — Sehat

> **Hardened by the Jun 29 adversarial audit — see `docs/AUDIT_FINDINGS.md` for the full rationale behind every
> stage below.** The headline change: **validation is the spine** (labeled cohort + AUC/KS/bad-rate), and a
> bureau hard-gate + fraud layer + canonical schema + consent artefacts sit around the scoring engine.

## Architecture diagram

```
  ULI (RBI data-pull rail IN, R2) ┐
   DATA SOURCES                    │           ┌──────────────────────────────────────────┐
   ┌──────────────┐  adapter (swap)│           │  PRE-SCORE PIPELINE (all can veto/cap)    │
   │ GST returns  │──┐             ▼           │  1 Consent artefact (ReBIT-style) valid?  │
   │ Bank txns(AA)│──┼─► DataSource ──► Canon-  │  2 Data-sufficiency gate (≥6mo, ≥2-4 GST) │
   │ UPI patterns │──┤   ├ MockSource(R1)  ical │  3 Fraud / anti-gaming (round-trip,spike) │
   │ EPFO (opt)   │──┘   └ SandboxSource │ schema│  4 Bureau / hygiene HARD-GATE             │
   └──────────────┘       (async AA      │(Pydan-│     (SMA/write-off/willful/enquiry vel.) │
                           consent SM)    │ tic)  └───────────────────┬──────────────────────┘
                                          ▼                           ▼ (pass)
                                   ┌──────────────┐          ┌────────────────────────┐
                                   │ FEATURE      │─────────►│  SCORING ENGINE         │
                                   │ ENGINE       │          │  6 sub-scores → FHS     │ weights FIT
                                   │ (pandas)     │          │  + reason codes         │ (logit), tested
                                   └──────────────┘          └───────┬─────────┬───────┘ monotonic
                                                                     │         │
                                          reason codes ──────────────┘         └── score + decision
                                                 ▼                                    ▼
                                  ┌──────────────────────────┐          ┌────────────────────────┐
                                  │ EXPLAINABILITY            │          │  DECISION LAYER        │
                                  │ templates default;        │          │  approve/refer/decline │
                                  │ Claude rephrases;         │          │  + indicative limit    │
                                  │ grounding-validated       │          │  (post-loan DSCR≥1.3-1.5)│
                                  └─────────┬─────────────────┘          └─────────┬──────────────┘
                                            └───────────┬──────────────────────────┘
                                                        ▼
                                  ┌──────────────────────────────────────────────┐
                                  │ AUDIT RECORD (immutable: input hash, scorecard │
                                  │ version, sub-scores, reason codes, model+prompt)│
                                  └───────────────────────┬────────────────────────┘
                                                          ▼
                              ┌────────────────────┐   ┌─────────────────────────────┐
                              │ HEALTH CARD UI      │   │ PORTFOLIO / BANK-SIDE VIEW   │
                              └────────────────────┘   └─────────────────────────────┘
                                                          │
                                  OCEN offer-OUT (approved limit + reason codes → LSPs, R2)

  ── Behind it all: a 300-1000 entity LABELED COHORT (latent propensity → noisy features + default label)
     → held-out AUC/KS/Gini + gains/lift + bad-rate AA→D monotone. This is the spine, built Jul 1-3. ──
```

## Synthetic data schema (matched to IDBI's three dataset categories)

Base shapes on **published specs** (Sahamati/AA, GSTR-1/3B, EPFO ECR) so the mock matches the real ecosystem,
not a guess. **Critical:** the Feature/Scoring/UI layers never read these raw shapes — they read the **canonical
Pydantic models** that `MockSource`/`SandboxSource` map into. A Jul-22 schema surprise is then contained in one
mapping function.

```jsonc
// 1) MSME financials  (entity + GST + EPFO)
{
  "entity": { "id":"M001","name":"Sharma Textiles","sector":"manufacturing",
              "state":"UP","reg_type":"NTC","gst_registered":true,"udyam_vintage_months":28 },
  "gst_returns": [ {"period":"2026-05","return_type":"GSTR-3B","filer_cadence":"monthly",
                    "turnover":820000,"tax_paid":41000,"is_nil":false,
                    "filed_on":"2026-06-18","due_on":"2026-06-20"} /* ...12 mo */ ],
  "epfo": { "available":true,"active":true,"employee_count":7,"monthly_contribution":18900,"since":"2024-09" }
  // epfo.available:false  ⇒ NEUTRAL (sub-threshold micro MSME), never a penalty
}
// 2) transactions  (bank/AA statement lines)
[ {"date":"2026-05-03","amount":24000,"type":"credit","balance_after":61250,
   "counterparty_id":"cp_4471","counterparty":"Verma Traders","channel":"UPI",
   "narration":"UPI/verma/...","category":"sales"} /* ... */ ]
// 3) upi_patterns  (monthly aggregates)
[ {"period":"2026-05","inflow_count":142,"inflow_amount":690000,"outflow_count":88,
   "outflow_amount":510000,"unique_payers":63,"unique_payees":29,
   "top1_payer_share":0.18,"top3_payer_share":0.41,"peak_day_share":0.11} ]
// 4) consent artefact  (ReBIT-style; refuse to score without a valid unexpired one)
{ "consentId":"c_91af","consentStart":"2026-07-01","consentExpiry":"2026-07-31",
  "FITypes":["DEPOSIT","GST_RETURNS"],"Purpose":{"code":"101","text":"credit assessment"},
  "fetchType":"PERIODIC","DataLife":{"unit":"MONTH","value":3},"consentMode":"STORE" }
// 5) bureau / hygiene  (mocked R1 — the HARD-GATE inputs; proprietor-level, not just firm)
{ "bureau_file":true,"cibil":742,"sma_status":null,"recent_writeoff":false,
  "settlement":false,"willful_defaulter":false,"enquiries_6m":2 }
// 6) latent label  (generator-only; NEVER shown on the card — drives validation)
{ "true_propensity":0.78,"defaulted_12m":false }
```

## The labeled cohort (the validation spine — build this, not just 4 personas)
Generate **300–1000 entities**. Each gets a hidden `true_propensity` that drives BOTH the observable features
(with noise) AND a seeded `defaulted_12m` label. Hold out a slice; report **AUC / KS / Gini**, a **gains/lift
table**, and **bad-rate monotonically decreasing AA→D**. Fit the 6 weights via **logistic regression** on the
cohort, then round for interpretability → "weights are fit, not guessed." Add **monotonicity tests** (perturb
one input worse → no sub-score or FHS improves) + a sensitivity table. The 4–6 demo personas are drawn from /
consistent with this cohort — **freeze persona inputs BEFORE running the engine; never tune inputs to fix a score.**

## Personas to generate (switchable live on Demo Day)
1. **Strong formal MSME** — clean books, high FHS, easy approve (baseline).
2. **Thin-file NTC hero** — clean bureau-positive proprietor, thin firm file → bureau scorecard can't price, Sehat approves with justification. **The winning case.**
3. **Volatile-cashflow borderline B** — refer/conditional; shows nuance.
4. **Genuine decline** — weak fundamentals; proves the model says no when it should.
5. **Thin-but-delinquent** — looks viable on alt-data but proprietor has live SMA/write-off → **bureau hard-gate correctly declines.** Shows bureau as necessary-but-insufficient.
6. **Partial-data / fraud-flagged** — missing sources → graceful "insufficient data" degradation; and/or round-tripping inflows the fraud layer catches and caps. Proves integrity + the data-coverage meter.

## Health Card UI layout

```
┌──────────────────────────────────────────────────────────────┐
│  Sharma Textiles · Manufacturing · UP   [● CREDIT-INVISIBLE]   │
│   FINANCIAL HEALTH         ┌── sub-scores (radar) ──┐          │
│        ╭───────╮           │   Cash-Flow      82    │          │
│        │  74   │  BAND A   │   Revenue        69    │          │
│        ╰───────╯           │   Discipline     88    │          │
│  RECOMMENDED ELIGIBILITY   │   Compliance     71    │          │
│  up to ₹6.0L (indicative)* │   Leverage       64    │          │
│  post-loan DSCR 1.4 ⓘ      │   Digital        77    │          │
│  ┌── STRENGTHS ──────────┐ └────────────────────────┘          │
│  │ ✓ 11/12 GST returns…  │  ┌── RISKS ───────────────────────┐ │
│  │ ✓ Zero bounced pmts…  │  │ ⚠ Revenue dipped 14% in Q1…    │ │
│  └───────────────────────┘  └────────────────────────────────┘ │
│  Data coverage: 12mo txns ✓  4 GST ✓  UPI ✓  EPFO n/a (micro)  │
│  Bureau gate: PASS (no SMA/default)     Fraud check: CLEAR      │
│  Sources: AA✓ GST✓ UPI✓     Consent c_91af valid → 2026-07-31  │
│  ── Conventional scorecard: thin/no file → can't price → decline│
│     Sehat: indicative approve, here's why ──  [Why this decision ▾]
│  *subject to KYC, credit policy & KFS — bank's sanction, not the score
│  Scorecard v1.3.0 · decision logged     [Request human review] │
│  ULI (data IN) ─► Sehat engine ─► OCEN (offer OUT)             │
└──────────────────────────────────────────────────────────────┘
```

## Round-1 schedule (now → Jul 9) — validation-first; **must ship a DEPLOYED app + GitHub + official PPT**

> **CORRECTED after the orientation (see ORIENTATION_NOTES.md):** Round 1 requires a **live deployment link +
> public GitHub repo + the official PPT template (fixed slides, unchangeable)** — not a deck+video. Deployment
> moves INTO Round 1. No demo video needed.

| Days | Build (Claude) | Human (Prakhar) |
|---|---|---|
| Jun 30 | scaffold repo; **canonical Pydantic schema** + adapter seam; cohort generator (labeled) | **Jun 30 deep-dive AMA: Track-03 specifics + mentor rejection criteria. Download the official PPT template; list its exact slides in DECK.md** |
| Jul 1–3 | **the spine:** scoring engine + reason codes, fit weights (logit), AUC/KS/bad-rate report, monotonicity tests; pre-score pipeline (consent, sufficiency, fraud, bureau gate) | sanity-check cohort realism; create public GitHub repo; pick deploy host |
| Jul 4–5 | decision layer (DSCR sizing) + audit record; explainability templates + grounding validator (Claude rephrase offline) | confirm IP/NDA terms on portal; feed Jun-30 answers back |
| Jul 6–7 | Health Card UI + demo personas (8 shipped, incl. the operational-proxy pair) + static portfolio view; **deploy live (Vercel web + hosted FastAPI)** | test the live link end-to-end; product calls, copy/tone |
| Jul 8 | **fill the official PPT template** (problem → live card → risk-qualified Lift → validation → controls → architecture → roadmap); polish deployed app + README | review deck against template rules; rehearse the walkthrough |
| Jul 9 | final pass; grounding/monotonicity tests green; freeze repo | **submit: PPT + deployment link + GitHub link** on Hack2skill |

> If a day slips: cut the portfolio view, then UI polish, then persona count — **never** the validation report,
> bureau gate, fraud layer, or the working deployment. A dead deploy link is worse than fewer features.

## Round-2 schedule (Jul 22 → 31) — a bounded integration task, not a config flag
- Day 1–2: map real sandbox payloads INTO the canonical schema (one mapping function); wire `SandboxSource` as the async AA consent state-machine.
- Day 3–5: integration proof — real data flows end to end into the card for the rails that actually work.
- Day 6–7: deploy ONE persona to a **real URL** on IDBI AWS/ACC; OCEN offer-out stub → real where possible.
- Day 8–9: harden, portfolio view on real data, finalize deployability story. Keep a **laptop-fallback demo**. Submit Jul 31.

## Open decisions / to pin later
- Claude model id for explainability: **plan to pin `claude-haiku-4-5`** (short rephrase task, not flagship) — confirm when writing the service. Narration pre-generated offline; zero live calls on the demo path.
- Final sub-score weights: **fit via logistic regression on the cohort**, then rounded — not hand-set. Document the fit.
- Loan-sizing constants: post-loan DSCR ≥ 1.3–1.5 + CV volatility haircut; **anchor exact numbers in the Jul 4–5 mentor's language.**
- Concentration (top-1/top-3 inflow share) as a **limit/band modifier**; small **sector-risk table** (uses the `sector` field) feeding seasonality expectation + limit modifier.
- Repo: monorepo `/engine` + `/web` + `/docs` (current plan).

## Deployment decision (LOCKED — don't re-litigate in the build session)

**Round 1 (live by Jul 9):**
- **Frontend:** Next.js on **Vercel** — zero-config, instant HTTPS URL, the "Final Product Link."
- **Engine:** FastAPI in a **Docker container on Render** (a *paid/always-on* instance, NOT the free tier).
  - Why always-on: the free tier spins down after ~15 min idle → a judge clicking a cold link waits ~50s. A
    dead-feeling link is worse than fewer features. A few dollars for July removes that risk entirely.
  - Alternatives if Render misbehaves: Railway or Fly.io (same Docker image, swap in ~30 min).
- **One monorepo**, two deploy targets. Manage CORS once (allow the Vercel origin).
- **No API key in the deployed env** — narration is pre-generated offline and shipped as static text in the
  persona JSON, so the live app makes zero LLM calls (also the demo-path rule from the audit).

**Round 2 (Jul 22–31):** rules mandate AWS/ACC. Because the engine is **Dockerized from day one**, the move is
just "run the same image on AWS App Runner / ECS Fargate" + point the frontend at the new URL — a bounded task,
not a rebuild. Keep the Vercel+Render deploy alive as the laptop-proof fallback.

**Rationale for a solo builder:** smallest reliable ops surface, both halves deploy independently, and the
container makes the AWS migration cheap. Don't gold-plate infra in Round 1 — the deploy exists to make the link
clickable, not to be production K8s.

## Files the audit added (write as we build)
- `docs/SUBMISSION_SPEC.md`, `docs/ELIGIBILITY.md` — fill from Jun 30 (gate everything).
- `docs/DECK.md`, `docs/DEMO_SCRIPT.md` — first-class artifacts once the spec is confirmed.
- `docs/GOVERNANCE.md` — data-fiduciary roles, fetch-minimization, retention/erasure, LLM PII boundary, RBI DLG mapping, drift/PSI monitoring, human-override/grievance. Source for the compliance slide.
