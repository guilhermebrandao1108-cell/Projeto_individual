"""Run the case-study permutation test on data exported by the ticket system.

Input: the CSV from `GET /metrics/export.csv` (sistema/backend), one row per ticket.

Pilot question, mirroring the case study: among tickets that received a proposed solution,
were those whose first reply missed the SLA reopened (solution rejected by the customer)
more often, comparing within the same queue?

    H0: within each queue, reopening is independent of meeting the first-response SLA.
    H1: the weighted difference in reopening rate (late − on time) is positive.

It reuses stats.make_strata / permutation_distribution / p_value, the same functions
validated against exact enumeration in tests/test_statistics.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import ALPHA, PERMUTATIONS, SEED
from .stats import make_strata, p_value, permutation_distribution

LATE = {'violado', 'vencido'}
PROPOSED = {'resolvido', 'fechado'}


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = {'fila', 'status', 'sla_primeira_resposta', 'reaberturas'} - set(df.columns)
    if missing:
        raise ValueError(f'CSV sem as colunas {sorted(missing)}: use a exportação de /metrics/export.csv')
    proposed = df['status'].isin(PROPOSED) | df['reaberturas'].gt(0)
    sample = df.loc[proposed].copy()
    # make_strata compares `days > threshold`; with threshold 0, days = 1 marks "first reply late".
    sample['days'] = sample['sla_primeira_resposta'].isin(LATE).astype(int)
    sample['unresolved'] = sample['reaberturas'].gt(0).astype(int)
    return sample


def run(path: str | Path, permutations: int = PERMUTATIONS, seed: int = SEED) -> dict:
    sample = load(path)
    tab, coverage = make_strata(sample, threshold=0, keys=['fila'])
    if tab.empty:
        raise ValueError('Nenhuma fila tem chamados no prazo e fora do prazo ao mesmo tempo: não há comparação possível')
    observed = float(tab['contribution'].sum() / tab['n'].sum())
    null = permutation_distribution(tab, permutations=permutations, seed=seed)
    p, extremes = p_value(null, observed)
    late, on_time = sample[sample['days'] == 1], sample[sample['days'] == 0]
    return {
        'tickets_with_proposal': len(sample),
        'queues_compared': int(len(tab)),
        'tickets_compared': coverage['included_rows'],
        'reopen_rate_late': float(late['unresolved'].mean()) if len(late) else None,
        'reopen_rate_on_time': float(on_time['unresolved'].mean()) if len(on_time) else None,
        'effect_pp': observed * 100,
        'permutations': permutations,
        'extreme_count': extremes,
        'p_value': p,
        'reject_h0': p <= ALPHA,
    }


def report(result: dict) -> str:
    br = lambda text: text.replace('.', ',')  # pt-BR decimals, as in the rest of the study
    pct = lambda v: '—' if v is None else br(f'{v:.1%}')
    decision = 'rejeita H0 a 5%' if result['reject_h0'] else 'não rejeita H0 a 5%'
    p_text = br(f"{result['p_value']:.4f}")
    return '\n'.join([
        'Piloto: primeira resposta fora do SLA × reabertura (estratos: fila)',
        f"  chamados com solução proposta: {result['tickets_with_proposal']}"
        f" · comparados: {result['tickets_compared']} em {result['queues_compared']} filas",
        f"  reabertura: fora do prazo {pct(result['reopen_rate_late'])} · no prazo {pct(result['reopen_rate_on_time'])}",
        br(f"  efeito estratificado: {result['effect_pp']:+.2f} pp"),
        f"  p = {p_text} ({result['extreme_count']} de {result['permutations']} permutações ≥ observado) → {decision}",
        '  Associação observacional: para medir o efeito do sistema, compare grupos com e sem o sistema (relatorio.md, seção 5).',
    ])
