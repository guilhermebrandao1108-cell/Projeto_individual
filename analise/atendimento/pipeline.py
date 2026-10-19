"""Run the full case study: load → describe → test → save metrics, aggregates and figures."""
from __future__ import annotations

import json
import platform

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import describe, plots
from .config import (ALPHA, BOOTSTRAP_REPLICATES, FIGURES_DIR, METRICS, PERMUTATIONS, PROCESSED_DIR,
                     REPORTS_DIR, SEED, SENSITIVITIES, STRATA_KEYS, THRESHOLD_DAYS)
from .data import analytic_sample, load_data, load_manifest
from .stats import cluster_bootstrap, make_strata, p_value, permutation_distribution, weighted_effect


def primary_test(analytic: pd.DataFrame) -> tuple[dict, np.ndarray]:
    """Pre-specified test: >7 vs 0–7 days within company × problem group."""
    tab, coverage = make_strata(analytic)
    observed = weighted_effect(tab)
    print(f'Primary strata: {len(tab)}; permutations: {PERMUTATIONS}', flush=True)
    null = permutation_distribution(tab)
    p, extremes = p_value(null, observed)
    ci, companies = cluster_bootstrap(tab)
    raw = analytic.groupby(analytic['days'].gt(THRESHOLD_DAYS))['unresolved'].agg(['size', 'sum', 'mean'])
    primary = {**coverage, 'threshold_days': THRESHOLD_DAYS, 'strata_keys': STRATA_KEYS, 'effect_pp': observed * 100,
               'crude_effect_pp': float((raw.loc[True, 'mean'] - raw.loc[False, 'mean']) * 100),
               'crude_same_overlap_effect_pp': float((tab['y1'].sum() / tab['n1'].sum() - tab['y0'].sum() / tab['n0'].sum()) * 100),
               'crude_groups': {'fast': {k: float(v) for k, v in raw.loc[False].items()}, 'slow': {k: float(v) for k, v in raw.loc[True].items()}},
               'permutations': PERMUTATIONS, 'seed': SEED, 'extreme_count': extremes, 'p_value': p,
               'alpha': ALPHA, 'reject_h0': bool(p <= ALPHA),
               'ci95_cluster_pp': ci, 'bootstrap_replicates': BOOTSTRAP_REPLICATES, 'bootstrap_seed': SEED + 1, 'companies_in_bootstrap': companies,
               'null_mean_pp': float(null.mean() * 100), 'null_sd_pp': float(null.std(ddof=1) * 100),
               'null_min_pp': float(null.min() * 100), 'null_max_pp': float(null.max() * 100)}
    return primary, null


def sensitivity_analyses(analytic: pd.DataFrame) -> list[dict]:
    """Descriptive robustness checks; no new confirmatory tests."""
    results = []
    for threshold, keys, label in SENSITIVITIES:
        tab, coverage = make_strata(analytic, threshold, keys)
        results.append({'label': label, 'threshold': threshold, 'keys': keys, 'effect_pp': weighted_effect(tab) * 100, **coverage})
    return results


def run() -> dict:
    for folder in [FIGURES_DIR, PROCESSED_DIR, REPORTS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    print('Reading and validating official archives...', flush=True)
    manifest = load_manifest()
    df = load_data(manifest)
    analytic = analytic_sample(df)

    quality = describe.quality(df, analytic)
    primary, null = primary_test(analytic)
    sensitivity = sensitivity_analyses(analytic)
    metrics = {'source': manifest['source'], 'cohort': manifest['cohort'], 'quality': quality, 'primary': primary, 'sensitivity': sensitivity,
               'software': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__, 'matplotlib': matplotlib.__version__},
               'interpretation': 'Associação observacional sob suposição de permutabilidade; não prova causalidade, necessidade comercial ou eficácia de software.'}
    METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

    # Aggregates only: no complaint-level rows or consumer attributes are saved.
    monthly, bands, seg = describe.monthly_counts(df), describe.response_bands(analytic), describe.segments(df)
    monthly.to_csv(PROCESSED_DIR / 'monthly_counts.csv', encoding='utf-8')
    bands.to_csv(PROCESSED_DIR / 'response_bands.csv')
    seg.to_csv(PROCESSED_DIR / 'segments.csv')
    pd.DataFrame({'permuted_effect_pp': null * 100}).to_csv(PROCESSED_DIR / 'permutation_null.csv', index=False)
    pd.DataFrame(sensitivity).drop(columns='keys').to_csv(PROCESSED_DIR / 'sensitivity.csv', index=False)

    plots.setup_style()
    plots.volume_mensal(monthly)
    plots.cobertura_e_resolucao(quality, primary['included_rows'])
    plots.tempo_e_desfecho(describe.time_distribution(df), bands)
    plots.segmentos(seg)
    plots.permutacao_e_efeito(null, primary)
    plots.sensibilidade(primary, sensitivity)
    plt.close('all')
    lo, hi = primary['ci95_cluster_pp']
    print(f"Efeito: {primary['effect_pp']:+.2f} pp · p = {primary['p_value']:.4f} · IC95% [{lo:.2f}; {hi:.2f}] pp", flush=True)
    return metrics
