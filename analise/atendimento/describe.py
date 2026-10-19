"""Data-quality indicators and descriptive aggregates (no inference here)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import THRESHOLD_DAYS, TIME_BANDS
from .data import evaluated_mask, valid_time_mask
from .stats import wilson


def quality(df: pd.DataFrame, analytic: pd.DataFrame) -> dict:
    evaluated, valid_time = evaluated_mask(df), valid_time_mask(df)
    answered = df['answered'].eq('S')
    evaluation_by_band = (df.loc[answered & valid_time]
                          .assign(slow=lambda x: x['days'].gt(THRESHOLD_DAYS), evaluated=lambda x: evaluated_mask(x))
                          .groupby('slow')['evaluated'].agg(['size', 'sum', 'mean']))
    return {'total_rows': len(df), 'months': int(df['month'].nunique()), 'companies': int(df['company'].nunique()),
            'segments': int(df['segment'].nunique()), 'answered_rows': int(answered.sum()),
            'not_answered_rows': int(df['answered'].eq('N').sum()), 'evaluated_rows': int(evaluated.sum()),
            'not_evaluated_rows': int(df['evaluation'].eq('Não Avaliada').sum()),
            'resolved_evaluated_rows': int(df['evaluation'].eq('Resolvida').sum()),
            'unresolved_evaluated_rows': int(df['evaluation'].eq('Não Resolvida').sum()),
            'evaluation_coverage': float(evaluated.mean()), 'analytic_rows': len(analytic),
            'missing_by_column': {k: int(v) for k, v in df.isna().sum().items()},
            'negative_time_rows': int(df['days'].lt(0).sum()),
            'nonfinite_nonmissing_time_rows': int((~np.isfinite(df['days']) & df['days'].notna()).sum()),
            'evaluated_not_answered_rows': int((evaluated & df['answered'].eq('N')).sum()),
            'evaluated_answered_invalid_time_rows': int((evaluated & answered & ~valid_time).sum()),
            'evaluated_answered_valid_missing_stratum_rows': int((evaluated & answered & valid_time & (df['company'].isna() | df['problem_group'].isna())).sum()),
            'time_summary_answered': df.loc[answered & valid_time, 'days'].describe(percentiles=[.25, .5, .75, .9, .95, .99]).to_dict(),
            'contacted_company_share': float(df['contacted'].eq('S').mean()),
            'unresolved_rate_among_evaluated': float(df.loc[evaluated, 'evaluation'].eq('Não Resolvida').mean()),
            'evaluation_by_primary_band': {str(k): {kk: float(vv) for kk, vv in row.items()} for k, row in evaluation_by_band.iterrows()}}


def monthly_counts(df: pd.DataFrame) -> pd.DataFrame:
    return (pd.crosstab(df['month'], df['evaluation'].fillna('Ausente'))
            .reindex(columns=['Resolvida', 'Não Resolvida', 'Não Avaliada', 'Ausente'], fill_value=0))


def time_distribution(df: pd.DataFrame) -> pd.Series:
    """Share of answered complaints (valid time) in each response-time band."""
    valid = df.loc[df['answered'].eq('S') & df['days'].ge(0), 'days']
    return pd.cut(valid, TIME_BANDS[0], labels=TIME_BANDS[1]).value_counts(sort=False)


def response_bands(analytic: pd.DataFrame) -> pd.DataFrame:
    """Crude unresolved rate per time band with Wilson 95% intervals."""
    rate = (analytic.assign(band=pd.cut(analytic['days'], TIME_BANDS[0], labels=TIME_BANDS[1]))
            .groupby('band', observed=False)['unresolved'].agg(['size', 'sum']))
    lo, hi = wilson(rate['sum'].to_numpy(), rate['size'].to_numpy())
    return rate.assign(rate=rate['sum'] / rate['size'], ci_lower=lo, ci_upper=hi)


def segments(df: pd.DataFrame) -> pd.DataFrame:
    seg = df.groupby('segment').agg(total=('evaluation', 'size'),
                                    evaluated=('evaluation', lambda x: x.isin(['Resolvida', 'Não Resolvida']).sum()),
                                    unresolved=('evaluation', lambda x: x.eq('Não Resolvida').sum())).sort_values('total', ascending=False)
    seg['rate_unresolved_evaluated'] = seg['unresolved'] / seg['evaluated']
    return seg
