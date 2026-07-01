# Sehat — the plain-English overview

> A jargon-free explainer of the whole project: what it is, the plan, and what's done.
> (The technical version lives in `CLAUDE.md` and the other `docs/`. This one is for reading like a human.)

## The competition
**IDBI Bank** runs a national hackathon, **Innovate 2026**, ~**₹15 lakh** in prizes. We entered **solo**
(Prakhar), team name **SehatAI**, in **Track 03** — about **lending and credit decisions**.

## The problem
When a small business (an **MSME** — a kirana store, a small textile shop) wants a loan, the bank checks
its **credit score** (CIBIL / bureau record). But millions of small businesses are **"credit-invisible"**:
they've never taken a formal loan, so they have no credit history. The bank's system sees nothing and
rejects them — even when the business is actually healthy and earning. They're stuck: can't get a loan
because they've never had a loan.

## What Sehat is
**Sehat** ("health") scores these businesses using **alternate data** instead of credit history:
- **GST returns** (tax filings → revenue)
- **UPI payments** (digital transactions → business activity)
- **Bank transactions** (cash flow → is the money steady?)
- **EPFO** (provident fund → do they have staff?)

From that it produces a **Financial Health Score (0–100)**, a decision (**approve / refer / decline**), and
an **explanation in plain English**. In short: *"the bureau can't see this business, but its bank account
and tax filings tell a clear story — and that story says it's a safe bet."*

## The one rule that makes a bank trust it
A bank will never deploy an AI that *guesses* at credit. So:
- **The math decides everything** — fixed rules, fully traceable, same input → same output.
- **The AI (Claude) only writes the explanations** — never the decision. A built-in checker blocks the AI
  from sneaking in a made-up number or twisting a "risk" into a "good thing."

The headline pitch: *"explainable AND it actually works AND a bank can govern it."*

## How it works (the assembly line)
1. **Consent check** — did the business agree to share this data? (legally required)
2. **Enough data?** — at least ~6 months of history.
3. **Fraud check** — catches gamed transactions (e.g. money shuffled back and forth to look busy).
4. **Bureau hard-gate** — if they *do* have a credit record and it's bad, reject regardless. (This is what
   makes the bank trust the whole thing.)
5. **Scoring** — six sub-scores (cash flow, revenue, banking discipline, compliance, leverage, digital
   activity) combine into the final score.
6. **Decision + loan size** — how much they could safely borrow.
7. **Explanation + audit record** — the plain-English reasons + a permanent, tamper-proof log.

## The thing that wins it
Not "we explain things" (5 teams will say that). The proof is the **Credit-Invisible Lift**: on a test set
of businesses a normal bank would *reject*, Sehat safely approved **41%** of them — and those only defaulted
**5.6%** of the time, vs **35%** for the ones it correctly declined. It **expands who the bank can lend to,
without taking on bad risk** — and it's backed by real statistics (AUC 0.78 = a standard "how well does this
separate good from bad" measure).

## The plan / timeline
- **Round 1 (Jul 9):** submit a **working deployed app** + public **GitHub repo** + a **slide deck**. Built
  entirely on our own realistic **fake (synthetic) data**.
- **Jul 21:** shortlist announced.
- **Round 2 (Jul 22–31):** shortlisted teams get the bank's **real sandbox data** + AWS. We swap our fake
  data source for the real one (designed to be a small, contained swap) and deploy on their cloud.
- **Aug 13:** Demo Day & winners.

## Who does what
- **Claude:** builds the code, fake data, scoring logic, website, docs, deck draft.
- **Prakhar (you):** attend sessions, ask mentors the right questions, make product calls, submit on the
  portal, present on Demo Day.

## What's been built
- **The engine (the brain):** fully built + tested — scoring, the safety gates, and the statistical proof. ✅
- **The last pieces (this session):** plain-English explanations + the AI-safety checker, the web server, the
  **website** (a polished bank-style "Health Card"), deployment files, README, governance doc, and tests. ✅
- **Two real problems found & fixed:** a math bug that made results not perfectly repeatable, and an "answer
  key" accidentally left inside the demo example files.

## What's left for you
1. Run one command (with your AI key) to add warmer wording — optional, it's safe without it.
2. Put it online (Vercel for the website, Render for the engine).
3. Fill the slide deck + record a 3-minute demo video.
4. Submit by **Jul 9**.

---

# The "AI/ML-driven" question (important — discussed with Prakhar)

The problem statement asks for an **"AI/ML-driven"** score. A fair challenge was raised: the current engine is
mostly hand-set *rules* with only the 6 final weights learned — and the LLM (Claude) only writes English, it
does NOT assess. So "AI/ML-driven" cannot rest on Claude. **The challenge was correct.** Decision: deepen the
real ML (see the Hybrid below), while keeping it explainable and bank-deployable.

## "Deterministic" and "Machine Learning" are NOT opposites
A trained model gives the **same answer every time** for the same input (deterministic *at decision time*),
yet it's still ML because its parameters were **learned from data**. Banks run models that are ML AND
deterministic AND auditable all at once. What we ruled out was letting the **LLM guess the decision** (a
black box that hallucinates) — NOT trained ML.

## The Hybrid strategy (two evaluators, like a real bank)
- **Champion — a learned Scorecard (WOE + Logistic Regression).** A points checklist ("steady income +20,
  files taxes on time +15, bounced cheques −25") where the points are **learned from data**, not guessed.
  You can read exactly why anyone scored what they did. **This makes the real decision** because it's
  transparent enough for a bank + regulator.
- **Challenger — a stronger model (monotonic Gradient Boosting + SHAP).** More powerful at subtle patterns;
  runs **alongside** as a cross-check / second opinion, with SHAP breaking each decision into "this factor
  +X, that one −Y." Both agree → high confidence; disagree → human review.
- **Pitch:** *"AI a bank is actually ALLOWED to use — a learned, explainable scorecard, cross-checked by a
  stronger model, with a human able to override on the record."* Beats pure-rules AND pure-black-box teams.

## Can a user change the result?
- **The MSME (applicant):** NO — never edits its own score/decision (that defeats the purpose). It can only
  **request a review** (appeal); a human decides.
- **The bank officer:** YES, but as an **override, not an edit** — the model's score stays frozen and logged;
  the officer can make a different final call, recorded with their name + reason + timestamp. RBI rules
  basically require this "human-in-the-loop with audit trail." (We have a "request review" button; the
  officer-override-with-logging flow is a candidate to add.)

## Why a black-box model "has nothing a bank can deploy"
A powerful black box (XGBoost/neural net) can be accurate (high AUC) but a bank still can't use it because:
1. **The law needs a reason for every rejection** — RBI Digital Lending rules require telling a rejected
   borrower *why*. A black box outputs "decline" but can't give a defensible reason. No reason → can't deploy.
2. **Governance/audit** — risk & compliance must sign off, decision by decision. You can't audit what you
   can't read.
3. **It can behave nonsensically** — e.g. "more bounced cheques → higher score" from a data quirk. (Our
   challenger uses **monotonic constraints** to forbid exactly that.)

So the prize isn't for the most accurate model — it's for a model a bank could actually **deploy**. Accuracy
is table-stakes; **deployability (explainability + governance + the law)** is where we win.

## "Aren't the logistic model and the neural net BOTH just predictions?" — yes, and here's the real difference
Correct — both are trained ML models that predict probability-of-default. The difference is NOT "one predicts,
one doesn't." It's **whether a human can READ the reasoning**:
- **Logistic regression = one short, readable equation** (`risk = −0.36×banking − 0.30×compliance − …`, one
  number per feature). You can print it on a slide and tell any borrower the exact reason for their score.
  **The model IS the explanation.**
- **Neural net / XGBoost = thousands–millions of tangled numbers** across many layers, with curves and
  interactions nobody wrote down. Predicts well, but the true "why" is "a 40,000-number calc came out low" —
  not a reason a bank can give.

One-liner: *both predict; the logistic model's reasoning is small enough to read and defend, the neural net's
is too tangled to read.* For credit, you need the readable one — the law requires explaining rejections.

Honest nuance: the readable model is slightly LESS accurate (only straight lines, misses subtle curves); the
powerful model is slightly more accurate but unreadable. So we let the **readable model decide + explain**
(satisfies the law) and run the **powerful model beside it as a check** (catches missed accuracy). **SHAP**
lets us peek inside the powerful one enough to sanity-check — not a full explanation, which is exactly why it
only *advises* and never decides. We don't pretend the black box is explainable; we use each for its strength.

## "Could we get REJECTED for being too simple?" — real risk, but the hybrid + framing flips it
- Two judge types: **technical screeners** may equate "sophisticated" with deep learning and could mark down a
  "logistic + rules" repo if they skim it (the genuine risk). **Banking/business judges** (our mentors' type)
  have lived "great model, compliance won't ship it" — they REWARD deployable+governable. A bank hackathon
  leans to the second, but we can't assume the first isn't in the room.
- The **hybrid neutralizes it**: gradient boosting (modern ML) + SHAP (state-of-the-art interpretability) +
  WOE/IV (bank credit-risk standard) + champion/challenger (how real risk teams operate) = NOT a simple
  submission. Anyone calling it "too simple" didn't read it — the deck makes sure they can't miss it.
- **Reframe is everything (same code, opposite impressions):** ❌ "we used logistic regression" (sounds lazy)
  vs ✅ "we deliberately let an explainable model steer — because RBI requires explaining every rejection —
  and cross-check it with a stronger challenger to prove we keep accuracy" (sounds like credit-risk expertise).
  Simplicity *chosen for a stated reason* = expertise; simplicity *by default* = laziness.
- **Our real moat:** most teams submit a model in a notebook; we have a complete deployed SYSTEM (data
  aggregation + fraud layer + consent + bureau gate + audit trail + validation + bank-grade UI + deployment).
  A whole working system is rarer and harder than one model — "too simple" is almost never the verdict on that.
- Caution the other way: don't add complexity just to look impressive (black box a bank can't deploy is the
  trap we're BEATING others on). Win = *sophisticated where it adds value, simple where the law demands.*

## "Where do the weights like −0.36 come from?" — learned from data, not typed in
The numbers are **fit (trained) by the computer**, not chosen by a human. How:
1. We have 1,000 businesses where we KNOW each one's 6 sub-scores AND whether it actually defaulted (a 0/1 label).
2. The formula has a blank weight per feature: `risk = w1×cashflow + w2×banking + …`.
3. The algorithm (`LogisticRegression().fit(X, y)`) tries weights, runs all 1,000 through the formula, measures
   how wrong it is vs the real "defaulted?" column, and **nudges each weight to reduce the error** — repeat
   thousands of times (gradient descent, like tuning radio dials to the clearest signal) until it settles.
4. The weights it lands on ARE those numbers. In our run the data said **banking discipline + compliance are
   the strongest repayment predictors** — we didn't decide that, the fit discovered it. (Negative signs just
   mean "high sub-score → low risk"; we flip to positive on the health card so higher = healthier.)

**Honest detail (good deck story):** left totally free, the fit zeroed out revenue & leverage (they overlap
with banking, so the math ignored them). A bank can't show a scorecard that says "we don't care about your
revenue." So we did what real credit teams do — **regularization + shrinkage toward sensible business
expectations** — keeping every dimension meaningful AND faithful to the data. Best answer to "how did you pick
the weights?": *"We didn't pick them — we fit them on a labelled cohort, then constrained them the way a
regulated scorecard must be."* (Today this trains on our synthetic data — it proves the METHOD; on the bank's
real sandbox data in Round 2 the same `.fit()` re-runs for real numbers. Same machinery, better data.)
