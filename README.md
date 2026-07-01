# Sehat — MSME Financial Health Card

> **IDBI Innovate 2026 · Track 03 (Financial Inclusion / Digital Lending / Credit Decisioning)**
> Team **SehatAI** · A deterministic, validated, governed credit-decisioning engine that scores
> credit-invisible MSMEs on alternate data — and *shows its work*.

Sehat aggregates a small business's alternate data — **GST returns, UPI patterns, Account-Aggregator
bank transactions, EPFO**, and — for the thinnest files — **operational proxies like electricity
consumption** — into a multidimensional, **fully explainable** Financial Health Score (FHS), and turns
it into an indicative credit decision a bank can govern. It approves thin-file businesses a bureau-only
scorecard would reject, while declining the ones it should — and proves, on a labelled cohort, that it
**separates good borrowers from bad**.

**Live demo:** _<add the Vercel URL on Slide 13>_ · **Engine API:** _<add the Render URL>_

---

## Why it wins

Five teams will claim "explainable." Sehat leads with the hard-to-copy combination:

1. **Explainable** — every number on the card is emitted by a deterministic engine and rendered from a
   controlled vocabulary of 48 reason codes. The LLM (Claude) *never decides anything*; it only rephrases
   a canonical template, and a **grounding validator** rejects any narration that introduces an
   unverified number or flips a risk into a strength, falling back to the template.
2. **Empirically separates good from bad** — on a held-out slice of a 1000-entity labelled cohort:
   **AUC 0.78, Gini 0.57, KS 0.46**, bad-rate **monotone AA→D**, and a risk-qualified
   **Credit-Invisible Lift**: across a thin-file *reject* cohort, Sehat safely approves **40.9%** at a
   **5.6%** bad rate vs **34.6%** for those it declines (**+17.2pt** vs blanket approval).
3. **A bank can govern it** — bureau hygiene **hard-gate** (SMA / write-off / willful-default → decline
   regardless of FHS), a **fraud / anti-gaming layer** (round-tripping, recency-spike, GST integrity),
   ReBIT-style **consent artefacts**, an **immutable audit record** (input hash, scorecard version,
   reason codes, model+prompt provenance), and a data-residency-safe LLM boundary.

For the very thinnest files, Sehat reads **operational proxies** — electricity / water / fuel meters.
Steady consumption corroborates that a business is genuinely operating at capacity even when its GST/UPI
file is too thin to price; a sharp drop flags a slowdown. The proxy is a **presence-gated** supplement
(it fires only when a meter series exists, and is out of the learned models by design), so it lifts the
thin-file cases without moving anything on the validated cohort. See the paired personas **P7**
(`/card/P7_PROXY_MFG`) — a genuinely credit-invisible manufacturer (no bureau file, thin GST, no UPI)
whose **steady electricity tips it to approve** — and **P7B** (`/card/P7B_PROXY_SLOWDOWN`), the same
business a quarter later whose **crashed meter flags a slowdown and steps the decision down to refer**.

## The six sub-scores

`FHS = Σ(weightᵢ × sub-scoreᵢ)` → bands **AA** 85+, **A** 70–84, **B** 55–69, **C** 40–54, **D** <40.
Weights are **fit via logistic regression** on the labelled cohort (then rounded for interpretability),
not guessed — and the fit *confirms* the design hierarchy.

| # | Sub-score | Fitted weight | Built from |
|---|---|---|---|
| 1 | Cash-Flow Health | 0.21 | bank txns + UPI |
| 2 | Revenue Vitality | 0.11 | GST + UPI |
| 3 | Banking Discipline | 0.26 | bank txns |
| 4 | Compliance & Formalization | 0.21 | GST + EPFO |
| 5 | Leverage & Obligations | 0.08 | AA / txns |
| 6 | Digital Footprint | 0.13 | UPI |

## Architecture

```
Data (GST / AA bank txns / UPI / EPFO / operational proxies)   [ULI = RBI data-pull rail IN, R2]
  → DataSource adapter  [MockSource R1 | SandboxSource R2]        ← the R1→R2 swap point
  → Canonical Pydantic schema (every layer below reads ONLY this)
  → Pre-score pipeline:  consent → data-sufficiency → fraud/anti-gaming → bureau hard-gate
  → Feature engine (pandas, independent of the generator → honest AUC)
  → Scoring engine (6 monotone sub-scores → FHS + reason codes; weights FIT via logit)
  → Decision layer (approve / refer / decline + indicative limit, post-loan DSCR ≥ 1.3–1.5)
      ‖ Explainability (templates by default; Claude rephrases OFFLINE; grounding-validated)
  → Immutable audit record
  → Health Card UI  +  Portfolio / bank-side view
  → OCEN offer-out (approved limit + reason codes → LSPs, R2)
```

The **canonical schema is the trick**: both `MockSource` (R1) and `SandboxSource` (R2) map raw payloads
into the same Pydantic models, so a sandbox schema surprise is contained in one mapping function, not
rippled through the engine. **ULI ≠ OCEN:** ULI pulls data *in*; OCEN sends the approved offer *out*.

## Repository layout

```
engine/                  Python + FastAPI scoring engine
  sehat/                 the package (schema, scoring, pipeline, decision, explain, audit, api, …)
  scripts/               cohort generator, weight fit + validation, persona freeze, segmentation, narration pre-gen, snapshot export
  personas/              8 FROZEN demo personas (+ pre-baked narration) — incl. the paired P7/P7B operational-proxy manufacturer
  artifacts/             validation_report.json, weight_fit.json, segmentation_report.json (deck evidence; cohort.jsonl is gitignored)
  Dockerfile             always-on container (zero LLM calls at serve time)
web/                     Next.js + Tailwind + Recharts Health Card + portfolio + validation pages
  lib/data/              static engine snapshots the UI bundles (bulletproof, backend-independent demo)
docs/                    strategy, build plan/status, audit findings, deck, governance, …
```

## Run it locally

**Engine + validation spine** (reproducible end-to-end):

```bash
cd engine
pip install -r requirements.txt
python scripts/generate_cohort.py --n 1000 --seed 42      # -> artifacts/cohort.jsonl (gitignored)
python scripts/generate_personas.py                       # -> personas/*.json (frozen)
python scripts/fit_and_validate.py --write-weights        # -> AUC/KS report + fitted weights
uvicorn sehat.api:app --reload                            # http://localhost:8000  (/personas /assess/{id} /validation /portfolio)
```

**Offline narration (optional — adds Claude rephrase to the cards):**

```bash
pip install anthropic
ANTHROPIC_API_KEY=...  python scripts/pregenerate_narration.py   # grounding-validated; falls back to templates
python scripts/export_snapshots.py                               # refresh the web UI's static data
```

**Web UI:**

```bash
cd web
npm install
npm run dev            # http://localhost:3000
npm run build          # static export -> web/out/ (deployable to Vercel)
```

The deployed app makes **zero live LLM calls** — narration is pre-generated offline and shipped as static
text; the web demo reads bundled engine snapshots so a backend outage can't break the card.

## Deploy

- **Web → Vercel** (Next.js static export; `web/vercel.json`). The "Final Product Link."
- **Engine → Render** (Docker, *always-on* — `render.yaml`; the same image moves to AWS in Round 2).
  Set `SEHAT_CORS_ORIGINS` to the Vercel origin.

## Determinism & governance

The score and decision are 100% rule/stat-based and auditable — see [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md)
for data-fiduciary roles (DPDP), fetch-minimization, the LLM PII boundary, RBI Digital-Lending mapping,
the audit schema, and the human-review/appeal path.

---

*Synthetic data calibrated to RBI/MSME distributions; pending sandbox validation. Output is **indicative
eligibility**, subject to KYC, credit policy and KFS — a binding sanction is the bank's act, not the score.*
Built by Prakhar (lead) with Claude. See [`CLAUDE.md`](CLAUDE.md) and [`docs/`](docs/) for the full record.
