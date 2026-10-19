"""Stratified permutation test, company-cluster bootstrap and Wilson intervals."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BOOTSTRAP_REPLICATES, PERMUTATIONS, SEED, STRATA_KEYS, THRESHOLD_DAYS


def make_strata(df: pd.DataFrame, threshold: int = THRESHOLD_DAYS, keys: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """2×2 counts per stratum (fast/slow × unresolved), keeping only strata with both bands."""
    keys = keys or STRATA_KEYS
    work = df.copy()
    work['slow'] = work['days'].gt(threshold).astype(int)
    grouped = work.groupby(keys + ['slow'], observed=True)['unresolved'].agg(['size', 'sum']).unstack('slow', fill_value=0)
    grouped = grouped.reindex(columns=pd.MultiIndex.from_product([['size', 'sum'], [0, 1]]), fill_value=0)
    tab = pd.DataFrame({'n0': grouped[('size', 0)], 'n1': grouped[('size', 1)],
                        'y0': grouped[('sum', 0)], 'y1': grouped[('sum', 1)]}).reset_index()
    overlap = tab['n0'].gt(0) & tab['n1'].gt(0)
    coverage = {'all_strata': len(tab), 'eligible_strata': int(overlap.sum()),
                'excluded_strata': int((~overlap).sum()),
                'excluded_rows': int(tab.loc[~overlap, ['n0', 'n1']].sum().sum())}
    tab = tab.loc[overlap].copy()
    tab['n'] = tab['n0'] + tab['n1']
    tab['delta'] = tab['y1'] / tab['n1'] - tab['y0'] / tab['n0']
    tab['contribution'] = tab['n'] * tab['delta']
    coverage['included_rows'] = int(tab['n'].sum())
    coverage['coverage_fraction'] = coverage['included_rows'] / len(df)
    return tab, coverage


def weighted_effect(tab: pd.DataFrame) -> float:
    """T = Σ (n_s / N) · (p_slow,s − p_fast,s)."""
    return float(tab['contribution'].sum() / tab['n'].sum())


def permutation_distribution(tab: pd.DataFrame, permutations: int = PERMUTATIONS, seed: int = SEED) -> np.ndarray:
    """Hypergeometric counts are exactly label permutations conditional on margins.

    For each stratum, A = unresolved labels assigned to slow records follows
    Hypergeom(total unresolved, total resolved, number slow). Margins/weights
    remain fixed. Vectorized batches bound memory, with no normal approximation.
    """
    rng = np.random.default_rng(seed)
    n = tab['n'].to_numpy(dtype=np.int64)
    n1, n0 = tab['n1'].to_numpy(dtype=np.int64), tab['n0'].to_numpy(dtype=np.int64)
    total_y = (tab['y0'] + tab['y1']).to_numpy(dtype=np.int64)
    weights = n / n.sum()
    null = np.empty(permutations)
    for start in range(0, permutations, 128):
        size = min(128, permutations - start)
        a = rng.hypergeometric(total_y, n - total_y, n1, size=(size, len(tab)))
        delta = a / n1 - (total_y - a) / n0
        null[start:start + size] = delta @ weights
    return null


def p_value(null: np.ndarray, observed: float) -> tuple[float, int]:
    """One-sided Monte Carlo p-value with the (b + 1) / (B + 1) correction."""
    extremes = int((null >= observed - 1e-14).sum())
    return (extremes + 1) / (len(null) + 1), extremes


def cluster_bootstrap(tab: pd.DataFrame, replicates: int = BOOTSTRAP_REPLICATES, seed: int = SEED + 1) -> tuple[list[float], int]:
    """Reweight whole companies, preserving the ratio-of-sums estimand."""
    cluster = tab.groupby('company')[['contribution', 'n']].sum()
    numerator, denominator = cluster['contribution'].to_numpy(), cluster['n'].to_numpy()
    rng = np.random.default_rng(seed)
    values = np.empty(replicates)
    for start in range(0, replicates, 128):
        size = min(128, replicates - start)
        idx = rng.integers(len(cluster), size=(size, len(cluster)))
        values[start:start + size] = numerator[idx].sum(axis=1) / denominator[idx].sum(axis=1)
    return (np.quantile(values, [.025, .975]) * 100).tolist(), len(cluster)


def wilson(k: np.ndarray, n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    p = k / n
    z = 1.959963984540054
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    radius = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return center - radius, center + radius
