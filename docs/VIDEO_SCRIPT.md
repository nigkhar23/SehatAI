# 3-minute demo video — teleprompter script + recording checklist

> **Format:** screen-recording of the LIVE site, your voice, no face needed.
> **Site:** https://sehat-ai-84ja.vercel.app/  · **Target length:** 2:45–3:00 (hard cap 3:00).
> **Read the bold lines aloud.** Italic = what to click/show. Word count ≈ 500 (≈150 wpm = ~2:58 — tight; keep the pace up).
> **Scene 2B is the operational-proxy beat (P7 → P7B)** — the exact alt-data source the Track-03 owner
> named on Jun 30, and it now shows the meter moving the decision *both ways* (approve → refer). If you
> run long, it's the highest-value 25 seconds — protect it and trim Scene 3 (P5) instead.

---

## SCENE 1 — The problem  (0:00–0:25)
_On screen: the Sehat home page (`/`)._

> **"Millions of small businesses in India — kirana stores, small manufacturers — have never taken a formal loan. So they have no credit-bureau history. When they apply, the bank's system sees nothing, and rejects them — even when the business is healthy and earning.**
> **This is Sehat. It scores those credit-invisible businesses using the data they already generate — GST returns, UPI payments, bank cash-flow — and it shows its work."**

---

## SCENE 2 — The winning case  (0:25–1:15)
_Click into the **P2 — Anita Provision Store** card (`/card/P2_HERO`). Let the gauge + radar load._

> **"Here's a real example. Anita's Provision Store — a thin-file business. A conventional bureau scorecard can't price it, so it would be declined.**
> **Sehat scores it 78 out of 100, Band A — and approves an indicative ₹13 lakh. And here's the point: it shows exactly why."**
_Scroll slowly down the strengths/risks._
> **"Steady inflows, a healthy operating surplus, on-time GST filing, no bounced payments — each one a clear, plain-English reason."**
_Scroll to the **Model cross-check** panel near the bottom._
> **"Underneath, two trained models cross-check the decision — a transparent scorecard a bank can read, and a stronger AI model as a second opinion. Both independently agree. High confidence."**

---

## SCENE 2B — Operational proxies  (1:15–1:40)
_Switch to **P7 — Verma Pressings** (`/card/P7_PROXY_MFG`). Scroll to the **electricity sparkline** panel._

> **"For the thinnest files, we go a step further. This manufacturer has no bureau file at all, thin GST, and no UPI — even alternate data is sparse. But look at its electricity meter: steady, month after month. That confirms the business is genuinely running at capacity — and that's what tips Sehat to approve it. This is exactly the operational-proxy signal your team asked about in the problem-statement session."**
_Switch to **P7B — the same business, a quarter later** (`/card/P7B_PROXY_SLOWDOWN`). Point at the falling sparkline._
> **"And here's the same business a quarter later — its electricity has dropped sharply. The very same signal now flags an operational slowdown, and Sehat steps the decision back down to 'refer.' The meter moves the decision both ways."**

---

## SCENE 3 — It says no, correctly  (1:40–2:05)
_Switch to **P5 — Patel Hardware** (`/card/P5_DELINQUENT`)._

> **"Just as important — it knows when to say no. Patel Hardware looks great on alternate data: a score of 86. But there's a live default marker on the proprietor's bureau record — so the hard-gate declines it, regardless of the score. The model isn't blind; the bureau is necessary, not optional. And when the two models disagree on a case, Sehat routes it to a human reviewer — governance built in."**

---

## SCENE 4 — Proof it works  (2:05–2:40)
_Go to the **Validation** page (`/validation`). Show the headline metrics, then the Lift box._

> **"This isn't a guess — it's validated. On a held-out test set, the score separates good borrowers from bad with an AUC of 0.78, and risk falls cleanly from band D up to AA.**
> **And the headline result: on the cohort a bureau would reject outright, Sehat safely approves 41% — at a 5.6% bad rate — versus 35% for the ones it declines. It expands who the bank can lend to, without taking on bad risk."**

---

## SCENE 5 — Why a bank can deploy it  (2:40–3:00)
_Scroll the validation page to the champion/challenger panel, or back to a card's "Why this decision" drawer._

> **"And every decision here is auditable. The maths decides; the AI only writes the explanation — and a validator stops it from inventing anything. Explainable, validated, and governable.**
> **That's the difference: not the most complex model, but AI a bank is actually allowed to deploy. Thank you."**
_End on the home page or the GitHub/links. Stop recording._

---

# 📋 One-page recording checklist

**Before you hit record**
- [ ] Close every other Chrome tab. Hide the bookmarks bar (`Ctrl+Shift+B`). Full-screen the browser.
- [ ] Open `https://sehat-ai-84ja.vercel.app/` and **pre-load** P2, **P7**, **P7B**, P5, and the validation page once (so they're warm — no loading flicker on camera). On P7 and P7B, scroll once to the electricity sparkline so you know where it sits — you'll toggle between the two.
- [ ] Plug in / test your mic. Record one 5-sec test, play it back — check you're audible and there's no echo.
- [ ] Have this script on your phone or a second screen (not covering the browser).

**Recording (Windows 11 — pick one)**
- [ ] **Xbox Game Bar:** press `Win + G` → Capture widget → mic ON → Record. Simplest.
- [ ] **Clipchamp** (pre-installed): "Record screen + mic" → lets you trim afterwards. Best if you want to cut mistakes.
- [ ] Speak calmly, slightly slower than feels natural. If you fumble a line, pause 2 sec and redo it — easy to trim.
- [ ] Watch the clock — the script is **~2:58, tight against the 3:00 hard cap**. Scene 4 (validation) is the must-keep. If you cross 3:00: first drop the P7B (slowdown) half of Scene 2B — keep the P7 steady→approve beat and just *say* "and the same meter flags a slowdown if consumption drops" without clicking through. That alone recovers ~15 sec. Trim Scene 3 (P5) next.

**After**
- [ ] Trim dead air at the start/end (Clipchamp, or YouTube's editor).
- [ ] Upload to **YouTube → Visibility: Unlisted** (not Private — judges must be able to watch via link).
- [ ] Title it: `SehatAI — IDBI Innovate 2026 — Track 03 Demo`.
- [ ] Copy the link → paste into **deck slide 13** ("Demo Video Link (3 Minutes)") → re-export deck to PDF.

**Pro tips**
- Move the mouse **deliberately and slowly** — jerky scrolling looks bad on video.
- Don't read the whole card aloud — narrate the *story*, let the visuals carry the detail.
- One clean take of ~3 min usually beats over-editing. If take 1 is 90% good, ship it.
- If your voice cracks on a word, it's fine — judges want substance, not polish.
