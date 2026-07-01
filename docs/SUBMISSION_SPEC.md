# Submission spec

> Status: **structure CONFIRMED from the official orientation** (see `docs/ORIENTATION_NOTES.md`). Exact slide
> list + caps must be read off the official PPT template on the portal. Building the wrong artifact = DQ.

## Round 1 (registration + submission both due Jul 9, 2026) — CONFIRMED from official instructions
**Three mandatory items to submit:**
1. **Deployment Link** — a live, working product URL. (Deploy by Jul 9 — see BUILD_PLAN.)
2. **GitHub Public Repository Link** — clean README, working code.
3. **Presentation/deck** — built on the official PPT template, **submitted as PDF.**
- The template is downloaded at `assets/idbi-innovate-2026-template.pptx`. Fill it → export to **PDF** → submit.
- The **3-min Demo Video Link**, GitHub link, and Final Product link are all **fields on slide 13** of the deck (referenced inside the deck, not separate uploads). Record the video anyway and put the link there.
- One submission maps to **exactly one** problem statement → Track 03.
- Round 1 runs on **our own mock data**; IDBI's synthetic datasets arrive only post-shortlist.

## Template slide list (CONFIRMED from the real .pptx — 13 content slides + 2 branding)
1 Team Details · 2 Brief about the idea · 3 Opportunities/differentiation/how-it-solves/USP · 4 Features ·
5 Process-flow/Use-case · 6 Wireframes (optional) · 7 Architecture · 8 Technologies · 9 Estimated cost (optional) ·
10 Prototype snapshots · 11 Performance/Benchmarking · 12 Additional/Future dev · 13 Links · 14–15 branding (image-only).
- **Slide 11 (Performance/Benchmarking)** is where our AUC/KS/bad-rate validation goes — a built-in slide that strongly rewards the validation-spine decision.
- Full slide-by-slide content plan: `docs/DECK.md`. Portal file-size cap / character limits: confirm at upload.

## Tech stack & cloud constraints — CONFIRMED (Jun-30 explainer, `docs/EXPLAINER_NOTES.md`)
- **No mandated language**; expect alignment with standard modern banking architecture.
- **Sandbox is on AWS** → Round 2 should use AWS-native services + the provided synthetic datasets + simulated
  bank APIs. GCP tools (BigQuery/Looker) are allowed **only** if they call cleanly *from* the AWS sandbox.
  → R1 deploy (Vercel web + Render engine) is fine for the shortlist; **plan an AWS-reachable path for R2.**
- **AI assistants permitted** (Claude/Cursor/ElevenLabs) if RBI-compliant, non-plagiarised, no copyright breach.
- **Compliance is a hard constraint on every submission:** RBI (AI/ML in credit), DPDP (consent/privacy),
  KYC/Aadhaar (SEBI/IRDAI for the wealth/insurance tracks). Our consent artefacts + audit trail are on-spec.

## Round 2 / Final (Jul 22 → 31)
- Refined prototype; sandbox + synthetic data + ACC support available here.
- (Confirm whether a new artifact set is required or it's an update of the R1 submission.)

## Timeline (per orientation host — supersedes earlier microsite guess where they differ)
- Jun 30 — problem-statement deep-dive + AMA. Jul 9 — register + submit. Jul 21 — shortlist.
- Jul 22–31 — refined prototype (sandbox). Aug 13 — finalists. Aug 21 — Demo Day + winners.

## Judging
- R1 vs R2 weighting / rubric: ❓ **OPEN — confirmed NOT stated in the Jun-30 session** (targeted pass).
  Also not in orientation. Exists only on the portal, if anywhere. Don't re-mine the videos.
- Evaluators: **IDBI's internal SMEs + business teams**; shortlisted solutions reviewed for **real-world pilot
  deployment**. Bank's internal stack is diversified legacy + its own secure cloud + on-prem, with KYC/Aadhaar/
  telecom-MNRL integrations — **AWS-compatible solutions integrate "without major architectural friction"**
  (Q10). → put "AWS-deployable, integrates with your internal cloud" on the deployability slide.
- Bank emphasis (reconfirmed Jun-30): scalability, feasibility, production-readiness, deployability at bank
  scale; **multi-dimensional data over single-stream** (an SMS-only or single-feed MVP was called
  insufficient); **explainability as decision-support** (AI must justify its "why"; human underwriter keeps
  the decision). Build to these — they ARE the rubric in spirit. See `docs/EXPLAINER_NOTES.md`.

_Last updated: Jun-30 explainer & AMA (video `sDGX-QvMyQo`) — see `docs/EXPLAINER_NOTES.md`._
