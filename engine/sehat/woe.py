"""Weight-of-Evidence (WOE) binning + Information Value (IV).

The bank-standard credit-risk transform, and the engine of the learned champion.
For each raw feature we split its range into bins and measure how risky each bin
ACTUALLY is on the labelled cohort:

  WOE(bin) = ln( (goods in bin / all goods) / (bads in bin / all bads) )
             ( "good" = repaid (y=0), "bad" = defaulted (y=1) )

A higher WOE = relatively more goods = lower risk. The Information Value

  IV = Σ_bins (good% - bad%) * WOE(bin)

scores how strongly the feature separates good from bad (the feature-ranking the
deck shows). This is what "data-learned thresholds" means: a human no longer picks
the ramp cut-points (0.12 / 0.60); the empirical default rate per bin sets them.

MONOTONE by construction (deployability): bins are merged until WOE is monotone in
the feature's known good-direction, so the learned scorecard can never encode a
non-monotone nonsense ("more bounces -> safer"). Missing values are a SEPARATE
neutral bin (WOE 0) — mirroring the FHS engine's "reweight, never penalise absence".

Pure numpy; deterministic given the data (no RNG). Training-time only — the serve
path reads the frozen bin table from champion.json and never imports this.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Laplace smoothing so a pure bin (all good or all bad) yields a finite WOE.
_SMOOTH = 0.5
# Initial fine bins (quantile) before monotone merging.
_INIT_BINS = 10
# Stability floor: every final bin must hold at least this fraction of rows.
_MIN_BIN_FRACTION = 0.05


@dataclass
class WOEBin:
    """One bin of a fitted feature. `lo`/`hi` are inclusive-exclusive edges; the
    first bin's lo is -inf and the last bin's hi is +inf so any value lands."""
    lo: float
    hi: float
    woe: float
    n: int
    n_bad: int
    bad_rate: float

    def to_dict(self) -> dict:
        return {"lo": self.lo, "hi": self.hi, "woe": round(self.woe, 6),
                "n": self.n, "n_bad": self.n_bad, "bad_rate": round(self.bad_rate, 6)}


@dataclass
class WOEFeature:
    """A fitted feature: its ordered numeric bins, the neutral missing bin, and IV."""
    key: str
    good_direction: int
    bins: list[WOEBin]
    missing_woe: float
    missing_n: int
    iv: float
    monotone: bool = True

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "good_direction": self.good_direction,
            "bins": [b.to_dict() for b in self.bins],
            "missing_woe": round(self.missing_woe, 6),
            "missing_n": self.missing_n,
            "iv": round(self.iv, 6),
            "monotone": self.monotone,
        }

    def woe_of(self, value: float | None) -> float:
        """Serve-time lookup also used in training/tests: value -> bin WOE."""
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return self.missing_woe
        for b in self.bins:
            if b.lo <= value < b.hi:
                return b.woe
        # value == +inf edge case (shouldn't happen; last bin hi is +inf)
        return self.bins[-1].woe if self.bins else 0.0


def _woe_iv(counts_good: np.ndarray, counts_bad: np.ndarray) -> tuple[np.ndarray, float]:
    """Smoothed WOE per bin + total IV from per-bin good/bad counts."""
    tot_good = counts_good.sum()
    tot_bad = counts_bad.sum()
    # Smoothed distributions (avoid div-by-zero / log(0)).
    dist_good = (counts_good + _SMOOTH) / (tot_good + _SMOOTH * len(counts_good))
    dist_bad = (counts_bad + _SMOOTH) / (tot_bad + _SMOOTH * len(counts_bad))
    woe = np.log(dist_good / dist_bad)
    iv = float(np.sum((dist_good - dist_bad) * woe))
    return woe, iv


def _initial_edges(x: np.ndarray) -> list[float]:
    """Quantile cut-points over observed (non-missing) values, deduped."""
    qs = np.linspace(0, 1, _INIT_BINS + 1)
    edges = np.unique(np.quantile(x, qs))
    if len(edges) < 2:                       # constant feature -> single bin
        return [-np.inf, np.inf]
    inner = [float(e) for e in edges[1:-1]]  # drop the min/max; interior cuts only
    return [-np.inf, *inner, np.inf]


def _bin_counts(x: np.ndarray, y: np.ndarray, edges: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Good/bad counts per [edge_i, edge_{i+1}) bin."""
    n = len(edges) - 1
    good = np.zeros(n)
    bad = np.zeros(n)
    for i in range(n):
        lo, hi = edges[i], edges[i + 1]
        mask = (x >= lo) & (x < hi)
        good[i] = int(np.sum(mask & (y == 0)))
        bad[i] = int(np.sum(mask & (y == 1)))
    return good, bad


def _is_monotone(woe: np.ndarray, good_direction: int) -> bool:
    """+1 feature: WOE must be non-decreasing across bins (higher value -> safer ->
    higher WOE). -1 feature: non-increasing. Single bin is trivially monotone."""
    if len(woe) <= 1:
        return True
    diffs = np.diff(woe)
    if good_direction >= 0:
        return bool(np.all(diffs >= -1e-9))
    return bool(np.all(diffs <= 1e-9))


def fit_feature(key: str, x_raw: np.ndarray, y: np.ndarray, good_direction: int) -> WOEFeature:
    """Fit a monotone WOE feature. `x_raw` may contain NaN (missing) — those rows go
    to the neutral missing bin and are excluded from the numeric binning."""
    x_raw = np.asarray(x_raw, dtype=float)
    y = np.asarray(y, dtype=int)
    miss = np.isnan(x_raw)
    missing_n = int(np.sum(miss))

    x = x_raw[~miss]
    yv = y[~miss]

    if len(x) == 0:
        # Everything missing: one all-neutral bin.
        return WOEFeature(key, good_direction, [WOEBin(-np.inf, np.inf, 0.0, 0, 0, 0.0)],
                          missing_woe=0.0, missing_n=missing_n, iv=0.0, monotone=True)

    edges = _initial_edges(x)
    min_count = max(1, int(_MIN_BIN_FRACTION * len(x)))

    # Greedy merge until (a) every bin is big enough AND (b) WOE is monotone.
    while True:
        good, bad = _bin_counts(x, yv, edges)
        woe, _ = _woe_iv(good, bad)
        n_bins = len(edges) - 1
        if n_bins <= 1:
            break

        # (a) Merge an undersized bin into its neighbour first (stability).
        totals = good + bad
        small = np.where(totals < min_count)[0]
        if len(small):
            i = int(small[0])
            drop = i + 1 if i == 0 else i      # remove the inner edge that merges i with a neighbour
            edges.pop(drop)
            continue

        # (b) Merge the first monotonicity-violating adjacent pair.
        if not _is_monotone(woe, good_direction):
            diffs = np.diff(woe)
            if good_direction >= 0:
                viol = np.where(diffs < -1e-9)[0]
            else:
                viol = np.where(diffs > 1e-9)[0]
            i = int(viol[0])                   # bins i and i+1 violate -> drop edge i+1
            edges.pop(i + 1)
            continue
        break

    good, bad = _bin_counts(x, yv, edges)
    woe, iv = _woe_iv(good, bad)
    bins: list[WOEBin] = []
    for i in range(len(edges) - 1):
        n_i = int(good[i] + bad[i])
        br = float(bad[i] / n_i) if n_i else 0.0
        bins.append(WOEBin(float(edges[i]), float(edges[i + 1]), float(woe[i]),
                           n_i, int(bad[i]), br))

    # Missing-bin WOE: kept NEUTRAL (0.0) by policy so absence is never a penalty,
    # exactly like the FHS reweighting rule. (We still record how many were missing.)
    return WOEFeature(key, good_direction, bins, missing_woe=0.0, missing_n=missing_n,
                      iv=float(iv), monotone=_is_monotone(woe, good_direction))
