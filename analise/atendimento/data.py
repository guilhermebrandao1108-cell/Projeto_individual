"""Load and validate the official archives; build the analytic sample."""
from __future__ import annotations

import hashlib
import json
import zipfile

import numpy as np
import pandas as pd

from .config import COLUMNS, MANIFEST, RAW_DIR


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def load_data(manifest: dict) -> pd.DataFrame:
    """Read every pinned ZIP, checking hashes, categories, dates and file/month agreement."""
    frames = []
    for file in manifest['files']:
        path = RAW_DIR / file['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != file['sha256']:
            raise ValueError(f'Hash mismatch: {path}')
        with zipfile.ZipFile(path) as archive:
            csvs = [x for x in archive.namelist() if x.endswith('.csv')]
            if len(csvs) != 1:
                raise ValueError('Expected one CSV per archive')
            frame = pd.read_csv(archive.open(csvs[0]), sep=';', encoding='utf-8-sig', usecols=list(COLUMNS)).rename(columns=COLUMNS)
        frame['source_month'] = file['file'][12:19]
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    for c in ['company', 'segment', 'problem_group', 'contacted', 'answered', 'evaluation']:
        df[c] = df[c].astype('string').str.strip().replace('', pd.NA)
    df['days'] = pd.to_numeric(df['days'], errors='coerce')
    df['date'] = pd.to_datetime(df['date'], errors='coerce', format='%Y-%m-%d')
    df['month'] = df['date'].dt.strftime('%Y-%m')
    if not df['evaluation'].dropna().isin(['Resolvida', 'Não Resolvida', 'Não Avaliada']).all():
        raise ValueError('Unexpected evaluation category: review schema before continuing')
    if not df['answered'].dropna().isin(['S', 'N']).all():
        raise ValueError('Unexpected answered category')
    if df['date'].isna().any() or not df['date'].dt.year.eq(2025).all():
        raise ValueError('Unexpected cohort dates')
    if not df['source_month'].eq(df['month']).all():
        raise ValueError('File/date mismatch')
    return df


def evaluated_mask(df: pd.DataFrame) -> pd.Series:
    return df['evaluation'].isin(['Resolvida', 'Não Resolvida'])


def valid_time_mask(df: pd.DataFrame) -> pd.Series:
    return np.isfinite(df['days']) & df['days'].ge(0)


def analytic_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Answered, explicitly evaluated, valid time and complete strata keys (plan, primary population)."""
    eligible = (evaluated_mask(df) & df['answered'].eq('S') & valid_time_mask(df)
                & df['company'].notna() & df['problem_group'].notna())
    analytic = df.loc[eligible].copy()
    analytic['unresolved'] = analytic['evaluation'].eq('Não Resolvida').astype(int)
    return analytic
