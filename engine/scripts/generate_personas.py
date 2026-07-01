"""Generate the 6 FROZEN demo personas (switchable live on Demo Day).

Each persona is generated once with a pinned propensity + targeted plan/bureau
overrides so it demonstrates a specific engine behaviour, then frozen as a JSON
file in `personas/`. CRITICAL (audit KEEP-AS-IS): persona inputs are frozen
BEFORE the engine runs — we never tune an input to fix a score. If a persona
doesn't land the intended decision, we fix the ENGINE or pick a different seed,
never hand-edit the persona's data.

Personas (from BUILD_PLAN.md):
  1 strong_formal      — clean books, high FHS, easy approve (baseline)
  2 thin_file_hero     — clean bureau-positive proprietor, thin FIRM file -> the winning case
  3 volatile_borderline— refer/conditional; shows nuance
  4 genuine_decline    — weak fundamentals; model correctly says no
  5 thin_delinquent    — looks viable on alt-data BUT proprietor has live SMA -> bureau hard-gate declines
  6 partial_fraud      — missing sources (graceful degradation) + round-tripping the fraud layer caps
  7 proxy_manufacturer — NEW-TO-CREDIT manufacturer (no bureau file, thin GST, no UPI),
                         STEADY electricity proxy tips it to approve (band A) -> the operational-
                         proxy ask (Track-03 owner, Jun 30). Genuinely credit-invisible.
  7B proxy_slowdown    — SAME business, electricity crashed -> RV_PROXY_TREND_BREAK -> refer
                         (band B). The paired 'toggle the meter' demo; proxy-blind models still
                         approve, so the FHS caught a slowdown they cannot see.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sehat.schema import ProxyType, RegType
from sehat.synth import generate_entity, _gen_operational_proxy

PERSONA_DIR = Path(__file__).resolve().parent.parent / "personas"


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def build_personas() -> list[dict]:
    personas: list[dict] = []

    # 1) Strong formal MSME — high propensity, clean everything.
    rec = generate_entity(
        _rng(101), "P1_STRONG", name="Sharma Textiles",
        propensity=0.90,
        plan_overrides={"base_monthly_revenue": 850_000,
                        "reg_type": RegType.PVT_LTD, "sector": "textiles",
                        "state": "UP", "vintage_months": 84, "headcount": 24,
                        "inflow_cv": 0.12, "surplus_ratio": 0.26,
                        "filing_ontime_prob": 1.0, "obligation_ratio": 0.10,
                        "top1_share": 0.18, "bounce_rate": 0.0, "months": 12,
                        "gst_count": 12},
        bureau_force={"bureau_file": True, "cibil": 768, "sma_status": None,
                      "recent_writeoff": False, "settlement": False,
                      "willful_defaulter": False, "enquiries_6m": 1},
    )
    personas.append({"persona": "strong_formal",
                     "tagline": "Clean formal MSME — straightforward approve (baseline).",
                     "record": rec.model_dump(mode="json")})

    # 2) Thin-file NTC hero — strong fundamentals, thin FIRM vintage, clean
    #    proprietor bureau. THE WINNING CASE: a conventional thin-file scorecard
    #    can't price it; Sehat approves on alternate data with justification.
    rec = generate_entity(
        _rng(102), "P2_HERO", name="Anita Provision Store",
        propensity=0.82,
        plan_overrides={"base_monthly_revenue": 420_000,
                        "reg_type": RegType.PROPRIETORSHIP, "sector": "retail_trade",
                        "state": "MH", "vintage_months": 11, "headcount": 3,
                        "inflow_cv": 0.16, "surplus_ratio": 0.22,
                        "filing_ontime_prob": 0.95, "obligation_ratio": 0.05,
                        "top1_share": 0.20, "bounce_rate": 0.0, "months": 12,
                        "gst_count": 6},
        bureau_force={"bureau_file": True, "cibil": 731, "sma_status": None,
                      "recent_writeoff": False, "settlement": False,
                      "willful_defaulter": False, "enquiries_6m": 2},
    )
    personas.append({"persona": "thin_file_hero",
                     "tagline": "Thin FIRM file — a firm-level scorecard can't price the business; "
                                "the proprietor's personal bureau is clean but blind to the firm's "
                                "live cash-flow. Sehat reads both and approves with reasons.",
                     "record": rec.model_dump(mode="json")})

    # 3) Volatile-cashflow borderline B — refer/conditional.
    rec = generate_entity(
        _rng(103), "P3_BORDERLINE", name="Kumar Logistics",
        propensity=0.55,
        plan_overrides={"base_monthly_revenue": 600_000,
                        "reg_type": RegType.PARTNERSHIP, "sector": "logistics",
                        "state": "GJ", "vintage_months": 30, "headcount": 9,
                        "inflow_cv": 0.52, "surplus_ratio": 0.11,
                        "filing_ontime_prob": 0.7, "obligation_ratio": 0.28,
                        "top1_share": 0.46, "bounce_rate": 0.02, "months": 12,
                        "gst_count": 8},
        bureau_force={"bureau_file": True, "cibil": 688, "sma_status": None,
                      "recent_writeoff": False, "settlement": False,
                      "willful_defaulter": False, "enquiries_6m": 4},
    )
    personas.append({"persona": "volatile_borderline",
                     "tagline": "Volatile inflows, moderate leverage — refer/conditional, shows nuance.",
                     "record": rec.model_dump(mode="json")})

    # 4) Genuine decline — weak fundamentals across the board.
    rec = generate_entity(
        _rng(104), "P4_DECLINE", name="Failing Traders",
        propensity=0.18,
        plan_overrides={"base_monthly_revenue": 280_000,
                        "reg_type": RegType.PROPRIETORSHIP, "sector": "wholesale_trade",
                        "state": "RJ", "vintage_months": 14, "headcount": 1,
                        "inflow_cv": 0.85, "surplus_ratio": -0.05,
                        "filing_ontime_prob": 0.35, "obligation_ratio": 0.45,
                        "top1_share": 0.62, "bounce_rate": 0.12, "months": 9,
                        "gst_count": 4},
        bureau_force={"bureau_file": True, "cibil": 602, "sma_status": None,
                      "recent_writeoff": False, "settlement": False,
                      "willful_defaulter": False, "enquiries_6m": 7},
    )
    personas.append({"persona": "genuine_decline",
                     "tagline": "Weak fundamentals — model correctly declines (filter, not approval machine).",
                     "record": rec.model_dump(mode="json")})

    # 5) Thin-but-delinquent — strong-looking alt-data BUT proprietor has a live
    #    SMA-2. The bureau HARD-GATE must decline regardless of a good FHS.
    rec = generate_entity(
        _rng(105), "P5_DELINQUENT", name="Patel Hardware",
        propensity=0.72,  # alt-data looks good...
        plan_overrides={"base_monthly_revenue": 500_000,
                        "reg_type": RegType.PROPRIETORSHIP, "sector": "retail_trade",
                        "state": "TN", "vintage_months": 22, "headcount": 4,
                        "inflow_cv": 0.20, "surplus_ratio": 0.20,
                        "filing_ontime_prob": 0.9, "obligation_ratio": 0.12,
                        "top1_share": 0.24, "bounce_rate": 0.0, "months": 12,
                        "gst_count": 6},
        bureau_force={"bureau_file": True, "cibil": 640, "sma_status": 2,  # ...but live SMA-2
                      "recent_writeoff": False, "settlement": False,
                      "willful_defaulter": False, "enquiries_6m": 5},
    )
    personas.append({"persona": "thin_delinquent",
                     "tagline": "Healthy alt-data but a live SMA-2 on the proprietor "
                                "— bureau hard-gate correctly declines (necessary-but-insufficient).",
                     "record": rec.model_dump(mode="json")})

    # 6) Partial-data + fraud-flagged — UPI & EPFO missing (graceful degradation)
    #    AND round-tripping inflows the fraud layer must cap.
    rec = generate_entity(
        _rng(106), "P6_FRAUD_PARTIAL", name="Mystery Exports",
        propensity=0.60,
        plan_overrides={"base_monthly_revenue": 450_000,
                        "reg_type": RegType.PROPRIETORSHIP, "sector": "wholesale_trade",
                        "state": "DL", "vintage_months": 16, "headcount": 2,
                        "inflow_cv": 0.30, "surplus_ratio": 0.15,
                        "filing_ontime_prob": 0.8, "obligation_ratio": 0.10,
                        "top1_share": 0.28, "bounce_rate": 0.01, "months": 12,
                        "gst_count": 4},
        bureau_force={"bureau_file": True, "cibil": 705, "sma_status": None,
                      "recent_writeoff": False, "settlement": False,
                      "willful_defaulter": False, "enquiries_6m": 3},
        inject_round_trip=True,
        drop_sources=("upi", "epfo"),
    )
    personas.append({"persona": "partial_fraud",
                     "tagline": "Missing UPI/EPFO (graceful degradation) + round-tripping inflows "
                                "the fraud layer detects and caps.",
                     "record": rec.model_dump(mode="json")})

    # 7 + 7B) OPERATIONAL-PROXY MANUFACTURER — the alt-data source the Track-03 owner
    #    named twice (Jun 30), shipped as a PAIR of cards (same business, two quarters):
    #      P7  = steady electricity  -> the proxy CORROBORATES a thin-file approve
    #      P7B = electricity crashed -> the SAME meter mechanism flags a slowdown -> refer
    #
    #    This is a GENUINELY credit-invisible file (the fix for the Jul-1 review findings):
    #    NO bureau file at all (bureau_file=False, no CIBIL), thin GST (3 returns), and NO
    #    UPI — a business a conventional scorecard literally cannot price. The proprietor is
    #    new-to-credit, so the bureau hard-gate emits BG_THIN_FILE (not a decline) and Sehat
    #    assesses purely on alternate data. Fundamentals are solid-but-thin, so the FHS sits
    #    right at the A/B boundary (~72) — which is exactly what lets the electricity signal
    #    be DECISION-RELEVANT: steady tips it to approve (A), a crash pulls it to refer (B).
    #
    #    Honest, documented properties (audit KEEP-AS-IS — inputs frozen BEFORE scoring, seed
    #    _rng(107), decision is whatever emerged; NEVER hand-tuned to fix a score):
    #      * The champion (proxy-blind WOE scorecard) approves; the challenger (monotone GBM)
    #        is CAUTIOUS on the sparse thin file — a 2-of-3 cross-check. That is correct model
    #        behaviour on thin data, and it routes to human review: the governance story, not
    #        a bug. We frame it that way on the card, we do not hide it.
    #      * On the crash card the FHS refers while the proxy-blind models still approve —
    #        i.e. the deterministic score caught a slowdown the bureau-style models cannot see.
    _P7_BUREAU_NTC = {"bureau_file": False, "cibil": None, "sma_status": None,
                      "recent_writeoff": False, "settlement": False,
                      "willful_defaulter": False, "enquiries_6m": 0}
    _P7_PLAN = {"base_monthly_revenue": 560_000,
                "reg_type": RegType.PROPRIETORSHIP, "sector": "manufacturing",
                "state": "GJ", "vintage_months": 16, "headcount": 6,
                "inflow_cv": 0.16, "surplus_ratio": 0.23,
                "filing_ontime_prob": 0.90, "obligation_ratio": 0.04,
                "top1_share": 0.40, "bounce_rate": 0.0, "months": 10,
                "gst_count": 3, "credits_per_month": 10}

    # P7 — steady meter (trend +2% over the window): proxy corroborates -> approve (band A).
    rng7 = _rng(107)
    proxy_steady = _gen_operational_proxy(
        rng7, months=10, proxy_type=ProxyType.ELECTRICITY,
        base_load=5200.0, trend=0.02, noise=0.04, unit="kWh",
    )
    rec = generate_entity(
        rng7, "P7_PROXY_MFG", name="Verma Pressings", propensity=0.70,
        plan_overrides=dict(_P7_PLAN), bureau_force=dict(_P7_BUREAU_NTC),
        drop_sources=("upi",), operational_proxy=[proxy_steady],
    )
    personas.append({"persona": "proxy_manufacturer",
                     "tagline": "New-to-credit manufacturer — no bureau file, thin GST, no UPI. A "
                                "conventional scorecard cannot price it, but steady metered electricity "
                                "confirms the unit is running at capacity, and Sehat approves on "
                                "alternate data.",
                     "record": rec.model_dump(mode="json")})

    # P7B — SAME business, SAME frozen inputs, but the electricity meter has fallen sharply
    #       (trend -55% -> a ~40%+ recent break): the RV_PROXY_TREND_BREAK risk fires and the
    #       FHS drops to band B -> refer. The proxy-blind champion still approves -> the score
    #       caught a slowdown the bureau-style model cannot see. Same seed stream so only the
    #       meter differs.
    rng7b = _rng(107)
    proxy_crash = _gen_operational_proxy(
        rng7b, months=10, proxy_type=ProxyType.ELECTRICITY,
        base_load=5200.0, trend=-0.55, noise=0.04, unit="kWh",
    )
    rec_b = generate_entity(
        rng7b, "P7B_PROXY_SLOWDOWN", name="Verma Pressings (Q-on-Q slowdown)", propensity=0.70,
        plan_overrides=dict(_P7_PLAN), bureau_force=dict(_P7_BUREAU_NTC),
        drop_sources=("upi",), operational_proxy=[proxy_crash],
    )
    personas.append({"persona": "proxy_slowdown",
                     "tagline": "The same manufacturer a quarter later — its electricity consumption "
                                "has fallen sharply. The same proxy that approved it now flags an "
                                "operational slowdown, and Sehat steps the decision down to refer.",
                     "record": rec_b.model_dump(mode="json")})

    return personas


def main() -> None:
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    personas = build_personas()
    for i, p in enumerate(personas, start=1):
        path = PERSONA_DIR / f"{i}_{p['persona']}.json"
        # Strip the latent label before freezing: demo personas are customer-facing
        # fixtures committed to the public repo, and the engine never validates against
        # them (the labelled COHORT keeps its labels for validation). The engine's
        # for_scoring() also strips it at runtime, so this is belt-and-suspenders —
        # but it keeps the served/committed JSON free of any "answer key."
        p["record"].pop("label", None)
        path.write_text(json.dumps(p, indent=2), encoding="utf-8")
        rec = p["record"]
        eid = rec["entity"]["id"]
        print(f"  {path.name:32s} {eid:16s} {p['persona']}")
    print(f"Wrote {len(personas)} frozen personas -> {PERSONA_DIR}")


if __name__ == "__main__":
    main()
