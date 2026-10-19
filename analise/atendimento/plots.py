"""Matplotlib figures for the case study: one function per figure, saved as PNG in figures/.

Each function receives ready-made tables (no calculations here) and returns the figure,
so the notebook can display it inline; the CLI closes them after saving.
"""
from __future__ import annotations

import textwrap

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

from .config import FIGURES_DIR, PERMUTATIONS

NAVY, TEAL, CORAL, GRAY = '#143246', '#087e8b', '#d65e47', '#71838d'
SOURCE = 'Fonte: Senacon / Consumidor.gov.br · Reclamações finalizadas em 2025 · Cálculos reproduzíveis do projeto.'
MONTHS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def br(value: float, decimals: int = 2) -> str:
    """Format numbers in pt-BR: thousands with dot, decimals with comma."""
    return f'{value:,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


BR_AXIS = mtick.FuncFormatter(lambda x, _: br(x, 0) if float(x).is_integer() else br(x, 1))


def setup_style() -> None:
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 19,
                         'axes.titleweight': 'bold', 'axes.titlecolor': NAVY, 'axes.labelcolor': NAVY,
                         'text.color': NAVY, 'xtick.color': GRAY, 'ytick.color': GRAY,
                         'axes.spines.top': False, 'axes.spines.right': False, 'axes.spines.left': False,
                         'axes.edgecolor': '#d9e0e4', 'figure.facecolor': '#fafcfd', 'axes.facecolor': '#fafcfd',
                         'grid.color': '#dce4e8', 'grid.alpha': .6, 'savefig.dpi': 160})


def save(fig: plt.Figure, name: str, footnote: str, left: float = .10) -> plt.Figure:
    fig.text(.04, .025, footnote, fontsize=8, color=GRAY, va='bottom')
    fig.subplots_adjust(bottom=.18, top=.85, left=left, right=.96)
    fig.savefig(FIGURES_DIR / f'{name}.png', facecolor=fig.get_facecolor())
    return fig


def volume_mensal(monthly: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(12, 6.5))
    bottom = np.zeros(len(monthly))
    for col, color in zip(monthly.columns, [TEAL, CORAL, '#b8c7cf', '#e2cfb3']):
        ax.bar(np.arange(len(monthly)), monthly[col] / 1000, bottom=bottom, label=col, color=color, width=.67)
        bottom += monthly[col].to_numpy() / 1000
    ax.set(xticks=np.arange(12), xticklabels=MONTHS, ylabel='Reclamações (mil)', title='Volume e avaliação ao longo de 2025')
    ax.legend(ncol=4, frameon=False, loc='upper left', fontsize=10); ax.grid(axis='y'); ax.set_axisbelow(True)
    return save(fig, '01_volume_mensal', SOURCE + '\nNão avaliada não comprova solução; “Ausente” corresponde a quatro registros sem classificação de avaliação.')


def cobertura_e_resolucao(quality: dict, included_rows: int) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5), gridspec_kw={'width_ratios': [1.15, 1]})
    labels = ['Todas as finalizadas', 'Respondidas', 'Com avaliação\nexplícita', 'Amostra analítica', 'Com sobreposição\nnos estratos']
    counts = [quality['total_rows'], quality['answered_rows'], quality['evaluated_rows'], quality['analytic_rows'], included_rows]
    axes[0].barh(np.arange(5), np.array(counts) / 1e6, color=[NAVY, GRAY, TEAL, TEAL, CORAL], height=.6)
    axes[0].invert_yaxis(); axes[0].set(yticks=np.arange(5), yticklabels=labels, xlabel='Milhões de reclamações')
    axes[0].set_xlim(0, max(counts) / 1e6 * 1.38); axes[0].xaxis.set_major_formatter(BR_AXIS)
    for i, c in enumerate(counts): axes[0].text(c / 1e6 + .03, i, br(c, 0), va='center', fontsize=9)
    vals = [quality['resolved_evaluated_rows'], quality['unresolved_evaluated_rows']]
    axes[1].bar(['Resolvida', 'Não resolvida'], np.array(vals) / sum(vals) * 100, color=[TEAL, CORAL], width=.55)
    for i, v in enumerate(vals): axes[1].text(i, v / sum(vals) * 100 + 1, f'{br(v / sum(vals) * 100, 1)}%', ha='center', weight='bold')
    axes[1].set(ylabel='% entre avaliações explícitas', ylim=(0, 100)); axes[1].grid(axis='y'); axes[1].set_axisbelow(True)
    fig.suptitle('Quanto sabemos sobre a resolução?', fontsize=19, weight='bold', x=.52)
    fig.subplots_adjust(wspace=.55)
    return save(fig, '02_cobertura_e_resolucao', SOURCE + '\nAs etapas têm critérios distintos; “avaliada” pode incluir não respondidas. Taxa entre avaliadas difere do índice oficial.', left=.20)


def tempo_e_desfecho(distribution: pd.Series, bands: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5))
    share = distribution / distribution.sum() * 100
    axes[0].bar(distribution.index.astype(str), share, color=[TEAL]*3+[CORAL]*2)
    axes[0].set(xlabel='Tempo oficial de resposta (dias)', ylabel='% das respondidas com tempo válido', title='Distribuição do tempo', ylim=(0, share.max() * 1.22))
    p, lo, hi = bands['rate'], bands['ci_lower'], bands['ci_upper']
    axes[1].errorbar(np.arange(len(bands)), p*100, yerr=[(p-lo)*100, (hi-p)*100], fmt='o', color=CORAL, capsize=4, markersize=8)
    # Points (not bars) need no zero baseline; a 40–70% window makes the non-monotonic shape legible.
    axes[1].plot(np.arange(len(bands)), p*100, color=CORAL, linewidth=1, alpha=.45)
    for i, v in enumerate(p): axes[1].text(i, v*100 + 1.6, f'{br(v*100, 1)}%', ha='center', fontsize=10, weight='bold')
    axes[1].set(xticks=np.arange(len(bands)), xticklabels=bands.index.astype(str), ylim=(40, 70), xlabel='Tempo oficial de resposta (dias)', ylabel='% não resolvida entre avaliadas elegíveis', title='Associação observada')
    for ax in axes: ax.grid(axis='y'); ax.set_axisbelow(True)
    fig.subplots_adjust(wspace=.35)
    return save(fig, '03_tempo_e_desfecho', SOURCE + '\nTaxas brutas, eixo direito começa em 40%; IC95% Wilson (estreitos pelo volume) pressupõem independência. Tempo oficial desconta análise do gestor.')


def segmentos(seg: pd.DataFrame) -> plt.Figure:
    top = seg.head(8).iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(12, 7.5), sharey=True, gridspec_kw={'width_ratios': [1.3, 1]})
    y = np.arange(len(top)); labels = ['\n'.join(textwrap.wrap(x, 35)) for x in top.index]
    axes[0].barh(y, top['total'] / 1000, color=NAVY, height=.55)
    axes[0].set(yticks=y, yticklabels=labels, xlabel='Reclamações finalizadas (mil)')
    axes[0].xaxis.set_major_formatter(BR_AXIS)
    axes[1].scatter(top['rate_unresolved_evaluated'] * 100, y, color=CORAL, s=70)
    axes[1].set(xlim=(0, 100), xlabel='% não resolvida entre avaliadas')
    for i, v in enumerate(top['rate_unresolved_evaluated']): axes[1].text(v*100+2, i, f'{br(v*100, 1)}%', va='center')
    fig.suptitle('A dor varia entre segmentos', fontsize=19, weight='bold', x=.59)
    fig.subplots_adjust(wspace=.15)
    return save(fig, '04_segmentos', SOURCE + '\nOito maiores segmentos por volume. Volume não mede risco: não há denominador de clientes/transações.', left=.28)


def permutacao_e_efeito(null: np.ndarray, primary: dict) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5), gridspec_kw={'width_ratios': [1.3, 1]})
    observed, ci = primary['effect_pp'], primary['ci95_cluster_pp']
    axes[0].hist(null * 100, bins=45, color=TEAL, edgecolor='white', linewidth=.3)
    axes[0].axvline(observed, color=CORAL, linewidth=2.5)
    axes[0].text(observed - .12, .97, f'Observado\n{br(observed)} pp', transform=axes[0].get_xaxis_transform(), ha='right', va='top', color=CORAL, weight='bold')
    axes[0].text(observed - .12, .84, 'nenhuma permutação\nchegou a esse valor', transform=axes[0].get_xaxis_transform(), ha='right', va='top', fontsize=9.5, color=GRAY)
    axes[0].text(1.0, .55, f"Distribuição sob H₀\nB = {br(PERMUTATIONS, 0)} permutações\np unilateral = {br(primary['p_value'], 4)}", transform=axes[0].get_xaxis_transform(), va='center', fontsize=10,
                 bbox={'facecolor': 'white', 'edgecolor': '#d9e0e4', 'pad': 7})
    axes[0].set(xlabel='Diferença ponderada de não resolução (pp)', ylabel='Permutações', title='Referência sob H₀')
    axes[0].xaxis.set_major_formatter(BR_AXIS); axes[0].yaxis.set_major_formatter(BR_AXIS)
    effects = [primary['crude_same_overlap_effect_pp'], observed]
    axes[1].scatter(effects, [1, 0], color=[GRAY, CORAL], s=70, zorder=3)
    axes[1].errorbar(observed, 0, xerr=[[observed-ci[0]], [ci[1]-observed]], color=CORAL, capsize=6, linewidth=2)
    axes[1].axvline(0, color=GRAY, linestyle='--', linewidth=1)
    axes[1].set(yticks=[1, 0], yticklabels=['Bruto', 'Estratificado'], ylim=(-.8, 1.8), xlim=(-.5, 8), xlabel='Diferença (lentas − rápidas), pp', title='Magnitude e incerteza')
    axes[1].xaxis.set_major_formatter(BR_AXIS)
    axes[1].text(effects[0], 1.2, f'{br(effects[0])} pp', ha='center', color=GRAY, weight='bold')
    axes[1].text(observed, .2, f'{br(observed)} pp', ha='center', color=CORAL, weight='bold')
    axes[1].text(observed, -.38, f'IC95% por empresas: {br(ci[0])} a {br(ci[1])} pp', ha='center', fontsize=10)
    fig.subplots_adjust(wspace=.4)
    return save(fig, '05_permutacao_e_efeito', SOURCE + '\n>7 vs 0–7 dias; bruto e ajustado na mesma amostra com sobreposição. Permutação empresa × problema; IC por empresas.')


def sensibilidade(primary: dict, sensitivity: list[dict]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(12, 6.5))
    effects = [primary['effect_pp']] + [s['effect_pp'] for s in sensitivity]
    labels = ['Primária: >7 dias · empresa × problema'] + [s['label'] for s in sensitivity]
    ax.barh(np.arange(len(labels)), effects, color=[CORAL] + [TEAL]*len(sensitivity), height=.55)
    ax.invert_yaxis(); ax.axvline(0, color=GRAY, linewidth=1)
    ax.set(yticks=np.arange(len(labels)), yticklabels=labels, xlabel='Diferença ponderada de não resolução (pp)', title='Sensibilidade às escolhas analíticas')
    for i, v in enumerate(effects): ax.text(v+.15 if v>=0 else v-.15, i, ('+' if v >= 0 else '') + f'{br(v)} pp', va='center', ha='left' if v>=0 else 'right')
    ax.set_xlim(min(0, min(effects)) - (.5 if min(effects) >= 0 else 2), max(0, max(effects)) + 1.5)
    ax.xaxis.set_major_formatter(BR_AXIS)
    return save(fig, '06_sensibilidade', SOURCE + '\nAnálises descritivas pré-especificadas; as amostras com sobreposição podem mudar. Não são novos testes confirmatórios.', left=.38)
