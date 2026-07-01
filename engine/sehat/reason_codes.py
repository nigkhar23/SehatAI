"""Canonical reason-code registry — the controlled vocabulary of the engine.

Every signal the engine surfaces (strength, risk, gate trip, fraud flag) is a
ReasonCode with a stable machine code, a polarity, and an English TEMPLATE with
named slots. This is load-bearing for the determinism principle:

  * The engine emits ReasonHits (a code + the slot values it computed).
  * The default UI renders the template with those values — no LLM.
  * Claude may ONLY rephrase the rendered template, and the grounding validator
    asserts the rephrase reintroduces no number absent from the slots and never
    flips a RISK into a STRENGTH.

So the customer "never sees an unverified sentence." Codes are grouped by the
sub-score / gate that owns them. Templates use {slot} placeholders filled from
ReasonHit.values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Polarity(str, Enum):
    STRENGTH = "strength"
    RISK = "risk"
    NEUTRAL = "neutral"      # informational (e.g. data coverage notes)
    GATE = "gate"            # a hard-gate / pre-score outcome


@dataclass(frozen=True)
class ReasonCode:
    code: str
    polarity: Polarity
    template: str
    # Which sub-score or pipeline stage this belongs to (for grouping in the UI).
    domain: str
    # Slots the template expects; used by the grounding validator to know which
    # numbers are "authorised" to appear in narration.
    slots: tuple[str, ...] = field(default_factory=tuple)


# Registry keyed by code. Adding a code here makes it renderable everywhere.
REGISTRY: dict[str, ReasonCode] = {}


def _r(code: str, polarity: Polarity, domain: str, template: str, slots: tuple[str, ...] = ()):
    rc = ReasonCode(code=code, polarity=polarity, template=template, domain=domain, slots=slots)
    REGISTRY[code] = rc
    return rc


# --- Cash-Flow Health -------------------------------------------------------
_r("CF_INFLOW_CONSISTENT", Polarity.STRENGTH, "cash_flow",
   "Inflows are steady — month-to-month variation is low (CV {cv}).", ("cv",))
_r("CF_INFLOW_VOLATILE", Polarity.RISK, "cash_flow",
   "Inflows are volatile — month-to-month variation is high (CV {cv}).", ("cv",))
_r("CF_HEALTHY_SURPLUS", Polarity.STRENGTH, "cash_flow",
   "Operating surplus is healthy at {surplus_ratio_pct}% of inflows.", ("surplus_ratio_pct",))
_r("CF_THIN_SURPLUS", Polarity.RISK, "cash_flow",
   "Operating surplus is thin at {surplus_ratio_pct}% of inflows.", ("surplus_ratio_pct",))
_r("CF_STRONG_RUNWAY", Polarity.STRENGTH, "cash_flow",
   "Liquidity runway covers about {runway_months} months of outflows.", ("runway_months",))
_r("CF_SHORT_RUNWAY", Polarity.RISK, "cash_flow",
   "Liquidity runway is short — about {runway_months} months of outflows.", ("runway_months",))

# --- Revenue Vitality -------------------------------------------------------
_r("RV_GROWING_TURNOVER", Polarity.STRENGTH, "revenue_vitality",
   "GST turnover is trending up ({slope_pct}% over the observed window).", ("slope_pct",))
_r("RV_DECLINING_TURNOVER", Polarity.RISK, "revenue_vitality",
   "GST turnover is trending down ({slope_pct}% over the observed window).", ("slope_pct",))
_r("RV_GST_INFLOW_ALIGNED", Polarity.STRENGTH, "revenue_vitality",
   "Declared GST turnover aligns with observed bank inflows (ratio {alignment}).", ("alignment",))
_r("RV_SEASONAL", Polarity.NEUTRAL, "revenue_vitality",
   "Revenue shows a seasonal pattern (peak-to-trough ratio {seasonality}).", ("seasonality",))
# Operational-proxy signals (electricity/water/fuel). Supplementary: they fire only
# when a meter series is present, and confirm/contradict a thin GST+UPI revenue read.
_r("RV_PROXY_STABLE", Polarity.STRENGTH, "revenue_vitality",
   "Metered {proxy_type} consumption is steady — the business is operating at "
   "capacity even with a thin tax file.", ("proxy_type",))
_r("RV_PROXY_TREND_BREAK", Polarity.RISK, "revenue_vitality",
   "Metered {proxy_type} consumption fell {drop_pct}% over {window} months — "
   "a possible operational slowdown.", ("proxy_type", "drop_pct", "window"))

# --- Banking Discipline -----------------------------------------------------
_r("BD_NO_BOUNCES", Polarity.STRENGTH, "banking_discipline",
   "No bounced or returned payments over the observed period.", ())
_r("BD_BOUNCES", Polarity.RISK, "banking_discipline",
   "{bounce_count} bounced/returned payment(s) observed ({bounce_rate_pct}% of debits).",
   ("bounce_count", "bounce_rate_pct"))
_r("BD_NEG_BALANCE_DAYS", Polarity.RISK, "banking_discipline",
   "Account was negative/overdrawn on {neg_balance_days} day(s).", ("neg_balance_days",))
_r("BD_HEALTHY_BUFFER", Polarity.STRENGTH, "banking_discipline",
   "Maintains a minimum-balance buffer (median EOD balance ₹{median_balance:,.0f}).", ("median_balance",))

# --- Compliance & Formalization --------------------------------------------
_r("CO_ONTIME_FILING", Polarity.STRENGTH, "compliance",
   "{ontime_pct}% of GST returns filed on or before the due date.", ("ontime_pct",))
_r("CO_LATE_FILING", Polarity.RISK, "compliance",
   "Only {ontime_pct}% of GST returns filed on time.", ("ontime_pct",))
_r("CO_EPFO_ACTIVE", Polarity.STRENGTH, "compliance",
   "Active EPFO registration with {employee_count} employees (formalised workforce).",
   ("employee_count",))
_r("CO_EPFO_NEUTRAL", Polarity.NEUTRAL, "compliance",
   "EPFO not applicable below the 20-employee threshold — treated as neutral.", ())
_r("CO_GOOD_VINTAGE", Polarity.STRENGTH, "compliance",
   "Established operating history — {vintage_months} months of registered vintage.",
   ("vintage_months",))
_r("CO_THIN_VINTAGE", Polarity.RISK, "compliance",
   "Limited operating history — {vintage_months} months of registered vintage.",
   ("vintage_months",))

# --- Leverage & Obligations -------------------------------------------------
_r("LV_HEALTHY_DSCR", Polarity.STRENGTH, "leverage",
   "Comfortable debt-service capacity (DSCR proxy {dscr}).", ("dscr",))
_r("LV_TIGHT_DSCR", Polarity.RISK, "leverage",
   "Tight debt-service capacity (DSCR proxy {dscr}).", ("dscr",))
_r("LV_LOW_OBLIGATIONS", Polarity.STRENGTH, "leverage",
   "Existing obligations are a small share of inflows ({obligation_ratio_pct}%).",
   ("obligation_ratio_pct",))
_r("LV_HIGH_OBLIGATIONS", Polarity.RISK, "leverage",
   "Existing obligations consume {obligation_ratio_pct}% of inflows.", ("obligation_ratio_pct",))
_r("LV_DEBT_UNVERIFIED", Polarity.NEUTRAL, "leverage",
   "No recurring debt detected in bank data — treated as UNVERIFIED, not zero; "
   "bureau and GST-declared loans remain authoritative.", ())

# --- Digital Footprint ------------------------------------------------------
_r("DF_HIGH_VELOCITY", Polarity.STRENGTH, "digital_footprint",
   "Strong digital activity — {txn_velocity} UPI transactions/month on average.",
   ("txn_velocity",))
_r("DF_DIVERSE_COUNTERPARTIES", Polarity.STRENGTH, "digital_footprint",
   "Diversified customer base — {unique_counterparties} unique counterparties.",
   ("unique_counterparties",))
_r("DF_CONCENTRATED_PAYERS", Polarity.RISK, "digital_footprint",
   "Revenue concentration risk — top payer is {top1_share_pct}% of inflows.",
   ("top1_share_pct",))
_r("DF_THIN_FOOTPRINT", Polarity.RISK, "digital_footprint",
   "Limited digital footprint — {txn_velocity} UPI transactions/month.", ("txn_velocity",))

# --- Data sufficiency (gate) ------------------------------------------------
_r("DS_INSUFFICIENT_TXN", Polarity.GATE, "sufficiency",
   "Insufficient bank history — {txn_months} month(s) provided, {min_months} required.",
   ("txn_months", "min_months"))
_r("DS_INSUFFICIENT_GST", Polarity.GATE, "sufficiency",
   "Insufficient GST history — {gst_returns} return(s) provided, {min_returns} required.",
   ("gst_returns", "min_returns"))
_r("DS_REWEIGHTED", Polarity.NEUTRAL, "sufficiency",
   "Some signals were unavailable — affected sub-scores were reweighted, not zeroed.", ())
_r("DS_PROXY_USED", Polarity.NEUTRAL, "sufficiency",
   "Operational proxy ({proxy_type}) used to supplement a thin GST/UPI file.",
   ("proxy_type",))

# --- Consent (gate) ---------------------------------------------------------
_r("CN_VALID", Polarity.GATE, "consent",
   "Valid consent {consent_id} (purpose {purpose}) covering the data fetched, "
   "expiring {expiry}.", ("consent_id", "purpose", "expiry"))
_r("CN_MISSING", Polarity.GATE, "consent",
   "No valid consent artefact — refusing to score (ReBIT consent required).", ())
_r("CN_EXPIRED", Polarity.GATE, "consent",
   "Consent {consent_id} expired on {expiry} — refusing to score.", ("consent_id", "expiry"))
_r("CN_SCOPE_MISMATCH", Polarity.GATE, "consent",
   "Consent does not cover the requested FI types ({missing}) — refusing to score.",
   ("missing",))

# --- Fraud / anti-gaming (can veto/cap) -------------------------------------
_r("FR_ROUND_TRIPPING", Polarity.GATE, "fraud",
   "Possible round-tripping — ₹{gross} gross flow with {counterparty} nets to near zero.",
   ("gross", "counterparty"))
_r("FR_RECENCY_SPIKE", Polarity.GATE, "fraud",
   "Recent inflows ({recent_mean}) are {ratio}x the trailing baseline — trend score capped.",
   ("recent_mean", "ratio"))
_r("FR_PAYER_CONCENTRATION", Polarity.GATE, "fraud",
   "Inflows concentrated despite a high unique-payer count — possible inflation of the count.", ())
_r("FR_GST_INTEGRITY", Polarity.GATE, "fraud",
   "Observed inflows materially exceed declared GST turnover (ratio {ratio}) — integrity flag.",
   ("ratio",))
_r("FR_GST_NIL_TAX", Polarity.GATE, "fraud",
   "Turnover declared but effectively no GST paid across periods — integrity flag.", ())
_r("FR_CLEAR", Polarity.NEUTRAL, "fraud",
   "No fraud or anti-gaming flags detected.", ())

# --- Bureau / hygiene hard-gate ---------------------------------------------
_r("BG_PASS", Polarity.GATE, "bureau",
   "Bureau hygiene clear — no SMA, write-off, settlement or willful-default markers.", ())
_r("BG_SMA", Polarity.GATE, "bureau",
   "Bureau shows SMA-{sma} (special-mention) status — declined regardless of health score.",
   ("sma",))
_r("BG_WRITEOFF", Polarity.GATE, "bureau",
   "Bureau shows a recent write-off/settlement — declined regardless of health score.", ())
_r("BG_WILLFUL", Polarity.GATE, "bureau",
   "Borrower appears on a willful-defaulter / RBI-defaulter list — declined.", ())
_r("BG_ENQUIRY_VELOCITY", Polarity.RISK, "bureau",
   "High credit-enquiry velocity — {enquiries} enquiries in 6 months.", ("enquiries",))
_r("BG_THIN_FILE", Polarity.NEUTRAL, "bureau",
   "Thin/no bureau file — a conventional scorecard cannot price this borrower; "
   "Sehat assesses on alternate data instead.", ())


def get(code: str) -> ReasonCode:
    """Look up a reason code, raising a clear error for an unknown code."""
    try:
        return REGISTRY[code]
    except KeyError as exc:  # pragma: no cover - guards against typos at author time
        raise KeyError(f"Unknown reason code {code!r}. Register it in reason_codes.py.") from exc


def render(code: str, values: dict) -> str:
    """Render a reason code's template against computed slot values.

    Missing slots raise — a rendered sentence must never contain an empty/unverified
    placeholder. This is the deterministic backbone the LLM may only rephrase.
    """
    rc = get(code)
    try:
        return rc.template.format(**values)
    except KeyError as exc:
        raise KeyError(
            f"Reason code {code!r} template needs slot {exc} not present in {sorted(values)}"
        ) from exc
