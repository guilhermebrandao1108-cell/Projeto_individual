"""Paths and analysis parameters; values follow docs/plano_analise.md."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data/raw'
PROCESSED_DIR = ROOT / 'data/processed'
MANIFEST = ROOT / 'data/manifest.json'
FIGURES_DIR = ROOT / 'figures'
REPORTS_DIR = ROOT / 'reports'
METRICS = REPORTS_DIR / 'metrics.json'

CATALOG_URL = 'https://consumidor.gov.br/pages/publicacao/externo/publicacoes.json?indicadorTipoPublicacao=2'
SEED = 20251018
PERMUTATIONS = 9999
BOOTSTRAP_REPLICATES = 4999
ALPHA = .05
THRESHOLD_DAYS = 7
STRATA_KEYS = ['company', 'problem_group']
SENSITIVITIES = [
    (5, ['company', 'problem_group'], '>5 dias · empresa × problema'),
    (10, ['company', 'problem_group'], '>10 dias · empresa × problema'),
    (7, ['segment', 'problem_group'], '>7 dias · segmento × problema'),
]
TIME_BANDS = ([-.1, 2, 5, 7, 10, float('inf')], ['0–2', '3–5', '6–7', '8–10', '>10'])

# Only the columns needed for the analysis are read from the official CSVs.
COLUMNS = {'Data Finalização': 'date', 'Tempo Resposta': 'days', 'Nome Fantasia': 'company',
           'Segmento de Mercado': 'segment', 'Grupo Problema': 'problem_group',
           'Procurou Empresa': 'contacted', 'Respondida': 'answered',
           'Avaliação Reclamação': 'evaluation', 'Nota do Consumidor': 'rating'}
