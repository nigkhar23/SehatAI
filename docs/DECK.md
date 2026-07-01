# Deck — official IDBI Innovate 2026 PPT template (13 content slides, FIXED structure)

> **Team name: SehatAI** (locked). Team leader: Prakhar. Problem statement: Track 03 — MSME Financial Health Card.
>
> The real `.pptx` is saved at `assets/idbi-innovate-2026-template.pptx` (downloaded from the official Google
> Slides). It has **13 content slides** (1–13) + 2 image-only branding slides (14–15). Structure is fixed — fill
> each slide, don't restructure. **Submit as PDF** (fill PPT → export PDF).
>
> ## Mandatory submission items (Jul 9) — per official instructions
> 1. **Deployment Link** (live working product) — mandatory.
> 2. **GitHub Public Repository Link** — mandatory.
> 3. **Presentation/deck** built on this template, **submitted as PDF** — mandatory.
> - The **3-min Demo Video Link** is a field on slide 13 (referenced inside the deck), not a separate upload —
>   but we still record the video and put the link there. GitHub + Final Product links also live on slide 13.

## Slide-by-slide content plan (verbatim headings from the real template)

1. **Team Details** — Team name: **SehatAI** · Team leader: Prakhar · Problem Statement: **Track 03 — AI/ML MSME Financial Health Card (Financial Inclusion / Digital Lending / Credit Decisioning).**

2. **Brief about the idea** *(section heading; content lives on slide 3)*.

3. **Opportunities / How different / How it solves / USP** —
   - *Opportunities:* large unserved/underserved MSME segment; credit-invisible NTC/NTB units that bureau-only underwriting can't price.
   - *How different:* deterministic, validated, governed score; the LLM only narrates reason codes, never decides.
   - *How it solves:* aggregates alternate data (GST/UPI/AA/EPFO) → multidimensional explainable health score + indicative credit decision.
   - *USP:* "explainable AND empirically separates good from bad (AUC/KS validated) AND a bank can govern it" — bureau hard-gate + fraud layer + audit trail + consent artefacts.

4. **List of features** → 6 sub-scores; bureau hygiene hard-gate; fraud/anti-gaming layer; data-sufficiency gate + coverage meter; deterministic FHS with fitted weights; reason-code explainability (template + Claude rephrase, grounding-validated); indicative limit sizing (post-loan DSCR ≥1.3–1.5); immutable audit record + scorecard versioning; risk-qualified Credit-Invisible Lift; portfolio/bank-side view; AA consent artefact; ULI-in / OCEN-out integration points.

5. **Process flow / Use-case diagram** → pre-score pipeline: consent → sufficiency → fraud → bureau gate → feature engine → scoring → decision + explanation → audit → card.

6. **Wireframes/Mock diagrams (optional)** → Health Card UI mock + portfolio view mock.

7. **Architecture diagram** → full BUILD_PLAN architecture (sources → adapter/canonical schema → pipeline → engine → explainability/decision → audit → UI; ULI in / OCEN out; AWS deploy).

8. **Technologies** → Python, FastAPI, pandas/numpy, scikit-learn (logit weight fit); Next.js, React, Tailwind, Recharts; Pydantic canonical schema; Claude (claude-haiku-4-5) narration only; AWS (Round 2); deployed Vercel + hosted FastAPI (Round 1).

9. **Estimated implementation cost (optional)** → infra per-decision cost; LLM cost ≈ near-zero (narration cached/pre-generated, short text); scales sub-linearly. Cheap-per-assessment vs manual underwriting.

10. **Snapshots of the prototype** → screenshots of the live card (hero + decline + fraud-flagged personas); data-coverage meter; "Why this decision" drawer.

11. **Prototype Performance report/Benchmarking** → **THE SPINE SLIDE.** AUC / KS / Gini on held-out cohort; bad-rate monotone AA→D; gains/lift table; risk-qualified Credit-Invisible Lift (approve X% of a reject cohort at Y% bad rate). Caveat: "on synthetic data calibrated to RBI/MSME distributions, pending sandbox validation."

12. **Additional Details/Future Development** → Round-2 sandbox plan (1–2 rails live + AWS deploy); governance/compliance (DPDP, RBI Digital Lending, audit, human-review/appeal); portfolio analytics; pilot-cohort roadmap.

13. **Provide links to your:** GitHub Public Repository: _____ · Demo Video Link (3 Minutes): _____ · Final Product Link (deployment): _____ .

14–15. Image-only branding slides — leave as-is.

## Deliverables this forces (Round 1, by Jul 9)
- [ ] Public **GitHub repo** (clean README).
- [ ] **Deployed live product** (Final Product / Deployment Link).
- [ ] **3-minute demo video** (link on slide 13): problem → live card → Lift → validation.
- [ ] The **filled 13-slide deck → exported to PDF**.
