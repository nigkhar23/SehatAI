"""Validation — the spine. Discrimination metrics on the labeled cohort.

Computes AUC / KS / Gini, a gains/lift table, bad-rate by band (must be monotone
AA->D), and the risk-qualified Credit-Invisible Lift. The score must SEPARATE
good from bad on held-out data with an honest, not circular, AUC.

Convention: a HIGHER FHS means LOWER risk. We define a risk score = (100 - FHS)
so standard "higher score = more likely positive(=default)" metric code reads
naturally; AUC is computed on risk-score vs the default label.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


@dataclass
class GainsRow:
    decile: int
    n: int
    n_defaults: int
    bad_rate: float
    cum_defaults: int
    cum_pct_defaults: float
    lift: float


@dataclass
class BandRow:
    band: str
    n: int
    n_defaults: int
    bad_rate: float
    approve_rate_if_policy: float   # share this band contributes to approvals


@dataclass
class LiftResult:
    """Risk-qualified Credit-Invisible Lift over a thin-file 'reject' cohort.

    A conventional bureau-only scorecard cannot price thin/no-file borrowers and
    generically declines them. We ask: of THAT population, how many does Sehat
    approve, and at what realised bad rate?
    """
    reject_cohort_n: int
    sehat_approved_n: int
    approval_rate: float
    approved_bad_rate: float
    declined_bad_rate: float
    baseline_bad_rate: float
    # Counterfactual: defaults avoided vs approving the whole cohort blindly.
    bad_rate_reduction_vs_blanket: float


@dataclass
class ValidationReport:
    n: int
    n_train: int
    n_test: int
    base_default_rate: float
    auc: float
    gini: float
    ks: float
    ks_band: float
    gains: list[GainsRow]
    bands: list[BandRow]
    lift: LiftResult
    bad_rate_monotone: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def ks_statistic(y_true: np.ndarray, risk: np.ndarray) -> float:
    """Kolmogorov-Smirnov: max separation between cumulative good/bad distributions."""
    order = np.argsort(-risk)            # highest risk first
    y = y_true[order]
    n_bad = y.sum()
    n_good = len(y) - n_bad
    if n_bad == 0 or n_good == 0:
        return 0.0
    cum_bad = np.cumsum(y) / n_bad
    cum_good = np.cumsum(1 - y) / n_good
    return float(np.max(np.abs(cum_bad - cum_good)))


def gains_table(y_true: np.ndarray, risk: np.ndarray, n_bins: int = 10) -> list[GainsRow]:
    df = pd.DataFrame({"y": y_true, "risk": risk}).sort_values("risk", ascending=False)
    df = df.reset_index(drop=True)
    df["decile"] = pd.qcut(df.index, n_bins, labels=False, duplicates="drop") + 1
    total_defaults = max(1, int(df["y"].sum()))
    base_rate = df["y"].mean()
    rows: list[GainsRow] = []
    cum = 0
    for d, grp in df.groupby("decile"):
        nd = int(grp["y"].sum())
        cum += nd
        br = float(grp["y"].mean())
        rows.append(GainsRow(
            decile=int(d), n=int(len(grp)), n_defaults=nd, bad_rate=round(br, 4),
            cum_defaults=cum, cum_pct_defaults=round(cum / total_defaults, 4),
            lift=round(br / base_rate, 2) if base_rate > 0 else 0.0,
        ))
    return rows


def band_table(bands: np.ndarray, y_true: np.ndarray) -> tuple[list[BandRow], bool]:
    order = ["AA", "A", "B", "C", "D"]
    df = pd.DataFrame({"band": bands, "y": y_true})
    approve_total = int(((df["band"] == "AA") | (df["band"] == "A")).sum())
    rows: list[BandRow] = []
    bad_rates: list[float] = []
    for b in order:
        grp = df[df["band"] == b]
        if len(grp) == 0:
            continue
        br = float(grp["y"].mean())
        bad_rates.append(br)
        share = (int(((grp["band"] == "AA") | (grp["band"] == "A")).sum()) / approve_total
                 if approve_total else 0.0)
        rows.append(BandRow(band=b, n=int(len(grp)), n_defaults=int(grp["y"].sum()),
                            bad_rate=round(br, 4), approve_rate_if_policy=round(share, 4)))
    # Monotonicity: bad rate must be non-decreasing AA->D.
    monotone = all(bad_rates[i] <= bad_rates[i + 1] + 1e-9 for i in range(len(bad_rates) - 1))
    return rows, monotone


def credit_invisible_lift(df: pd.DataFrame) -> LiftResult:
    """df columns: thin_file(bool), decision(str), y(default 0/1)."""
    reject = df[df["thin_file"]]
    n = len(reject)
    baseline_bad = float(reject["y"].mean()) if n else 0.0
    approved = reject[reject["decision"] == "approve"]
    declined = reject[reject["decision"] != "approve"]
    appr_n = len(approved)
    appr_bad = float(approved["y"].mean()) if appr_n else 0.0
    decl_bad = float(declined["y"].mean()) if len(declined) else 0.0
    return LiftResult(
        reject_cohort_n=n,
        sehat_approved_n=appr_n,
        approval_rate=round(appr_n / n, 4) if n else 0.0,
        approved_bad_rate=round(appr_bad, 4),
        declined_bad_rate=round(decl_bad, 4),
        baseline_bad_rate=round(baseline_bad, 4),
        bad_rate_reduction_vs_blanket=round(baseline_bad - appr_bad, 4),
    )


def build_report(
    y_true: np.ndarray,
    fhs: np.ndarray,
    bands: np.ndarray,
    thin_file: np.ndarray,
    decisions: np.ndarray,
    n_train: int,
    notes: list[str] | None = None,
) -> ValidationReport:
    """Assemble the full report on a (held-out) slice."""
    risk = 100.0 - fhs
    auc = float(roc_auc_score(y_true, risk))
    gini = 2 * auc - 1
    ks = ks_statistic(y_true, risk)

    gains = gains_table(y_true, risk)
    band_rows, monotone = band_table(bands, y_true)
    # KS on band-level risk (coarser, for the deck).
    band_risk = np.array([{"AA": 0, "A": 1, "B": 2, "C": 3, "D": 4}.get(b, 2) for b in bands],
                         dtype=float)
    ks_band = ks_statistic(y_true, band_risk)

    lift = credit_invisible_lift(pd.DataFrame({
        "thin_file": thin_file, "decision": decisions, "y": y_true,
    }))

    return ValidationReport(
        n=len(y_true),
        n_train=n_train,
        n_test=len(y_true),
        base_default_rate=round(float(y_true.mean()), 4),
        auc=round(auc, 4),
        gini=round(gini, 4),
        ks=round(ks, 4),
        ks_band=round(ks_band, 4),
        gains=gains,
        bands=band_rows,
        lift=lift,
        bad_rate_monotone=monotone,
        notes=notes or [],
    )
