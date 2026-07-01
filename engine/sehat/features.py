"""Feature engine — derives scoring features from canonical records (pandas).

Reads ONLY canonical models (never raw source shapes). Produces a flat
`Features` object the scoring engine consumes. Each feature also carries an
`availability` map so the scoring layer can reweight (not zero) sub-scores whose
inputs are missing, and mark "insufficient data" honestly.

This path is deliberately INDEPENDENT of `synth.py`'s emission formulas: the
generator emits raw txn/GST/UPI lines from a latent propensity through noisy
channels; here we re-derive features by aggregation. The two never share a
formula, which is what makes the downstream AUC an honest test rather than a
tautology.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from sehat.config import RECENCY_SPIKE_WINDOW_DAYS
from sehat.schema import CanonicalRecord, TxnCategory, TxnType

# Operating outflow categories (exclude drawings, EMI, tax, bounces — handled
# separately so surplus and obligations don't double-count).
_OPERATING_DEBIT_CATEGORIES = {
    TxnCategory.PURCHASE, TxnCategory.RENT, TxnCategory.UTILITIES,
    TxnCategory.SALARY, TxnCategory.OTHER,
}


@dataclass
class Features:
    """Flat feature bundle. `None` means the signal could not be computed (the
    scoring layer treats that as 'reweight', not 'zero')."""

    # Coverage / sufficiency
    txn_months: int = 0
    gst_returns: int = 0
    has_txns: bool = False
    has_gst: bool = False
    has_upi: bool = False
    has_epfo_applicable: bool = False     # True only if EPFO is meaningfully expected
    has_bureau: bool = False

    # Cash-flow health
    inflow_cv: Optional[float] = None              # coefficient of variation of monthly inflow
    surplus_ratio: Optional[float] = None          # (inflow - operating outflow) / inflow
    runway_months: Optional[float] = None          # closing balance / mean monthly outflow

    # Revenue vitality
    turnover_slope_pct: Optional[float] = None     # % change of GST turnover across window
    gst_inflow_alignment: Optional[float] = None   # bank inflow / declared turnover (directional)
    seasonality: Optional[float] = None            # peak/trough monthly inflow ratio

    # Banking discipline
    bounce_count: int = 0
    bounce_rate: Optional[float] = None            # bounces / debit count
    neg_balance_days: Optional[int] = None
    median_balance: Optional[float] = None

    # Compliance & formalization
    filing_ontime_pct: Optional[float] = None
    epfo_active: bool = False
    employee_count: int = 0
    vintage_months: int = 0

    # Leverage & obligations
    dscr_proxy: Optional[float] = None             # surplus / observed debt service
    obligation_ratio: Optional[float] = None       # debt service / inflow
    recurring_obligation_detected: bool = False
    obligation_detection_confidence: float = 0.0   # 0-1, how clean the recurring pattern is

    # Digital footprint
    txn_velocity: Optional[float] = None           # mean UPI inflow txns / month
    unique_counterparties: Optional[int] = None
    top1_payer_share: Optional[float] = None
    top3_payer_share: Optional[float] = None
    upi_vintage_months: int = 0

    # Operational proxy (electricity/water/fuel) — SUPPLEMENTARY, presence-gated.
    # Populated only when the record carries a meter series; otherwise every field
    # stays at its default and no proxy component or reason code ever fires (so an
    # entity without a proxy scores byte-identically to before this signal existed).
    # DELIBERATELY NOT a model feature — see model_features.py.
    has_proxy: bool = False
    proxy_type: Optional[str] = None               # "electricity" | "water" | "fuel"
    proxy_unit: Optional[str] = None               # display unit (kWh / kL / L)
    proxy_trend_pct: Optional[float] = None         # slope of the meter series, % over window
    proxy_recent_break_pct: Optional[float] = None  # recent-window mean vs trailing baseline, %
    proxy_recent_window_months: int = 0             # months in the recent window (reason slot)

    # Raw aggregates reused by fraud layer / sizing (so they're computed once)
    mean_monthly_inflow: Optional[float] = None
    median_monthly_net_surplus: Optional[float] = None   # for loan sizing
    observed_monthly_debt_service: Optional[float] = None
    closing_balance: Optional[float] = None
    recent_inflow_mean: Optional[float] = None           # last RECENCY_SPIKE_WINDOW_DAYS
    baseline_inflow_mean: Optional[float] = None         # trailing baseline

    availability: dict[str, bool] = field(default_factory=dict)

    def coverage_fraction(self) -> float:
        """Fraction of the four primary sources present (for the coverage meter)."""
        present = sum([self.has_txns, self.has_gst, self.has_upi,
                       (self.epfo_active or not self.has_epfo_applicable)])
        return present / 4.0


def _monthly_inflow_series(txn_df: pd.DataFrame) -> pd.Series:
    credits = txn_df[txn_df["type"] == TxnType.CREDIT.value]
    if credits.empty:
        return pd.Series(dtype=float)
    return credits.groupby("ym")["amount"].sum()


def _monthly_outflow_series(txn_df: pd.DataFrame, categories: set[str]) -> pd.Series:
    debits = txn_df[(txn_df["type"] == TxnType.DEBIT.value) & (txn_df["cat"].isin(categories))]
    if debits.empty:
        return pd.Series(dtype=float)
    return debits.groupby("ym")["amount"].sum()


def _txn_dataframe(rec: CanonicalRecord) -> pd.DataFrame:
    rows = []
    for t in rec.txns:
        rows.append({
            "date": t.date,
            "ym": f"{t.date.year:04d}-{t.date.month:02d}",
            "amount": t.amount,
            "type": t.type.value,
            "cat": t.category.value,
            "balance_after": t.balance_after,
            "counterparty_id": t.counterparty_id,
            "channel": t.channel.value,
        })
    return pd.DataFrame(rows)


def _detect_recurring_obligations(txn_df: pd.DataFrame) -> tuple[float, bool, float]:
    """Detect recurring FIXED debits (same payee, ~same amount, monthly, low var).

    Returns (monthly_debt_service, detected, confidence). Honest: we do NOT parse
    EMIs from free text — we look for a stable monthly cadence to the same payee.
    Confidence reflects how clean the pattern is (low CV, present most months).
    """
    debits = txn_df[txn_df["type"] == TxnType.DEBIT.value].copy()
    if debits.empty:
        return 0.0, False, 0.0
    n_months = debits["ym"].nunique()
    if n_months < 3:
        return 0.0, False, 0.0

    best_service = 0.0
    best_conf = 0.0
    detected = False
    for payee, grp in debits.groupby("counterparty_id"):
        if payee is None:
            continue
        months_present = grp["ym"].nunique()
        if months_present < max(3, int(0.6 * n_months)):
            continue
        # One representative debit per month (largest, in case of multiple).
        per_month = grp.groupby("ym")["amount"].max()
        if len(per_month) < 3:
            continue
        mean_amt = per_month.mean()
        cv = per_month.std(ddof=0) / mean_amt if mean_amt > 0 else 1.0
        if cv <= 0.15:  # low variance -> looks like a fixed instalment
            coverage = months_present / n_months
            conf = float(max(0.0, min(1.0, (0.15 - cv) / 0.15)) * coverage)
            if mean_amt > best_service:
                best_service = float(mean_amt)
                best_conf = conf
                detected = True
    return best_service, detected, best_conf


def _proxy_features(proxies: list) -> dict:
    """Derive trend + recent-break from the FIRST operational-meter series present.

    Returns the keyword args to set on Features (empty dict if no usable series).
    `proxy_trend_pct` is the least-squares slope expressed as % of the mean across the
    whole window; `proxy_recent_break_pct` compares the last RECENT_WINDOW months' mean
    against the trailing baseline (negative => a drop, e.g. the "-40% over 3 months"
    slowdown). Both are derived ONLY here — they never become model features.
    """
    RECENT_WINDOW = 3
    if not proxies:
        return {}
    proxy = proxies[0]                       # one meter per entity in this build
    pts = sorted(proxy.series, key=lambda p: p.period)
    y = np.array([p.value for p in pts], dtype=float)
    if len(y) < 2 or y.mean() <= 0:
        # Series too short / all-zero to read a trend — record presence only.
        return {"has_proxy": True, "proxy_type": proxy.type.value, "proxy_unit": proxy.unit}

    x = np.arange(len(y), dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    trend_pct = float(slope * (len(y) - 1) / y.mean() * 100.0)

    recent_n = min(RECENT_WINDOW, len(y) - 1)   # leave >=1 month for the baseline
    recent_mean = float(y[-recent_n:].mean())
    baseline_mean = float(y[:-recent_n].mean())
    break_pct = (
        float((recent_mean - baseline_mean) / baseline_mean * 100.0)
        if baseline_mean > 0 else None
    )
    return {
        "has_proxy": True,
        "proxy_type": proxy.type.value,
        "proxy_unit": proxy.unit,
        "proxy_trend_pct": round(trend_pct, 1),
        "proxy_recent_break_pct": (round(break_pct, 1) if break_pct is not None else None),
        "proxy_recent_window_months": recent_n,
    }


def compute_features(rec: CanonicalRecord) -> Features:
    """Compute the full feature bundle for one canonical record."""
    f = Features()
    f.vintage_months = rec.entity.udyam_vintage_months

    # --- Bank txn-derived features ---
    if rec.txns:
        df = _txn_dataframe(rec)
        f.has_txns = True
        f.txn_months = df["ym"].nunique()

        inflow = _monthly_inflow_series(df)
        outflow_op = _monthly_outflow_series(df, {c.value for c in _OPERATING_DEBIT_CATEGORIES})
        total_outflow = df[df["type"] == TxnType.DEBIT.value].groupby("ym")["amount"].sum()

        if len(inflow) >= 2 and inflow.mean() > 0:
            f.inflow_cv = float(inflow.std(ddof=0) / inflow.mean())
            f.mean_monthly_inflow = float(inflow.mean())
            f.seasonality = float(inflow.max() / inflow.min()) if inflow.min() > 0 else None

        if f.mean_monthly_inflow:
            mean_op_out = float(outflow_op.mean()) if len(outflow_op) else 0.0
            f.surplus_ratio = (f.mean_monthly_inflow - mean_op_out) / f.mean_monthly_inflow

        # Recency-spike inputs (fraud layer reads these too).
        max_date = df["date"].max()
        cutoff = max_date - pd.Timedelta(days=RECENCY_SPIKE_WINDOW_DAYS)
        recent = df[(df["type"] == TxnType.CREDIT.value) & (df["date"] > cutoff)]
        baseline = df[(df["type"] == TxnType.CREDIT.value) & (df["date"] <= cutoff)]
        if not recent.empty:
            recent_months = max(1, recent["ym"].nunique())
            f.recent_inflow_mean = float(recent["amount"].sum() / recent_months)
        if not baseline.empty:
            base_months = max(1, baseline["ym"].nunique())
            f.baseline_inflow_mean = float(baseline["amount"].sum() / base_months)

        # Bounces / discipline.
        debit_count = int((df["type"] == TxnType.DEBIT.value).sum())
        f.bounce_count = int((df["cat"] == TxnCategory.BOUNCE.value).sum())
        f.bounce_rate = (f.bounce_count / debit_count) if debit_count else 0.0

        bal = df.dropna(subset=["balance_after"])
        if not bal.empty:
            f.neg_balance_days = int((bal["balance_after"] < 0).sum())
            f.median_balance = float(bal["balance_after"].median())
            f.closing_balance = float(bal.sort_values("date")["balance_after"].iloc[-1])
            mean_total_out = float(total_outflow.mean()) if len(total_outflow) else 0.0
            if mean_total_out > 0 and f.closing_balance is not None:
                f.runway_months = max(0.0, f.closing_balance / mean_total_out)

        # Recurring obligations (honest detection).
        svc, detected, conf = _detect_recurring_obligations(df)
        f.observed_monthly_debt_service = svc
        f.recurring_obligation_detected = detected
        f.obligation_detection_confidence = conf
        if f.mean_monthly_inflow and f.mean_monthly_inflow > 0:
            f.obligation_ratio = svc / f.mean_monthly_inflow
            surplus_abs = f.mean_monthly_inflow * (f.surplus_ratio or 0.0)
            f.dscr_proxy = (surplus_abs / svc) if svc > 0 else None

        # Median net surplus for loan sizing (inflow - operating out - debt svc).
        if len(inflow) >= 1:
            joined = pd.DataFrame({"inflow": inflow})
            joined["op_out"] = outflow_op.reindex(joined.index).fillna(0.0)
            joined["net"] = joined["inflow"] - joined["op_out"] - svc
            f.median_monthly_net_surplus = float(joined["net"].median())

    # --- GST-derived features ---
    if rec.gst_returns:
        f.has_gst = True
        f.gst_returns = len(rec.gst_returns)
        gdf = pd.DataFrame([{
            "period": g.period, "turnover": g.turnover, "tax_paid": g.tax_paid,
            "is_nil": g.is_nil, "ontime": g.filed_on_time,
        } for g in rec.gst_returns]).sort_values("period")

        ontime_vals = gdf["ontime"].dropna()
        if len(ontime_vals):
            f.filing_ontime_pct = float(ontime_vals.mean() * 100.0)

        nonzero = gdf[gdf["turnover"] > 0]
        if len(nonzero) >= 2:
            y = nonzero["turnover"].to_numpy(dtype=float)
            x = np.arange(len(y), dtype=float)
            slope = np.polyfit(x, y, 1)[0]
            mean_t = y.mean()
            # Express slope as % change across the whole window relative to mean.
            f.turnover_slope_pct = float((slope * (len(y) - 1)) / mean_t * 100.0) if mean_t > 0 else None

        # GST-vs-inflow alignment (directional, confound-aware): inflow/turnover.
        total_turnover = float(gdf["turnover"].sum())
        if f.mean_monthly_inflow and total_turnover > 0:
            mean_monthly_turnover = total_turnover / len(gdf)
            f.gst_inflow_alignment = float(f.mean_monthly_inflow / mean_monthly_turnover)

    # --- UPI-derived features ---
    if rec.upi:
        f.has_upi = True
        f.upi_vintage_months = len(rec.upi)
        udf = pd.DataFrame([u.model_dump() for u in rec.upi])
        f.txn_velocity = float(udf["inflow_count"].mean())
        f.unique_counterparties = int(udf["unique_payers"].max())
        f.top1_payer_share = float(udf["top1_payer_share"].mean())
        f.top3_payer_share = float(udf["top3_payer_share"].mean())
    elif rec.txns:
        # Fall back to txn-derived counterparty stats if UPI aggregates absent.
        df = _txn_dataframe(rec)
        credits = df[df["type"] == TxnType.CREDIT.value]
        if not credits.empty:
            f.txn_velocity = float(len(credits) / max(1, f.txn_months))
            shares = credits.groupby("counterparty_id")["amount"].sum()
            total = shares.sum()
            if total > 0:
                sorted_shares = (shares / total).sort_values(ascending=False)
                f.unique_counterparties = int(len(sorted_shares))
                f.top1_payer_share = float(sorted_shares.iloc[0])
                f.top3_payer_share = float(sorted_shares.iloc[:3].sum())

    # --- EPFO ---
    if rec.epfo and rec.epfo.available:
        f.has_epfo_applicable = True
        f.epfo_active = rec.epfo.active
        f.employee_count = rec.epfo.employee_count

    # --- Operational proxy (electricity/water/fuel) — presence-gated supplementary ---
    for k, v in _proxy_features(rec.operational_proxy).items():
        setattr(f, k, v)

    # --- Bureau presence (the gate reads the record directly; this is for coverage) ---
    f.has_bureau = rec.bureau is not None and rec.bureau.bureau_file

    f.availability = {
        "cash_flow": f.has_txns,
        "revenue_vitality": f.has_gst or f.has_upi,
        "banking_discipline": f.has_txns,
        "compliance": f.has_gst,
        "leverage": f.has_txns,
        "digital_footprint": f.has_upi or f.has_txns,
    }
    return f
