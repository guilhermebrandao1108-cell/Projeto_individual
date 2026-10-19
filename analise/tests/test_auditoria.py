"""Independent audit: recompute the published metrics from the raw ZIPs without the package's pipeline.

Reads the CSVs in chunks with its own code path and checks counts, the effect, the
p-value and the null SD (against the analytic hypergeometric variance). Skipped when
the raw files are absent; download them with `python -m atendimento baixar`.
"""
from collections import Counter
import json
import math
from pathlib import Path
import unittest
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = sorted((ROOT / 'data/raw').glob('finalizadas_2025-*.zip'))
COLS = ['Nome Fantasia', 'Grupo Problema', 'Tempo Resposta', 'Respondida', 'Avaliação Reclamação']


@unittest.skipUnless(len(RAW) == 12, 'dados brutos ausentes: rode python -m atendimento baixar')
class IndependentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.counts, cls.tables = Counter(), Counter()
        for path in RAW:
            with zipfile.ZipFile(path) as z:
                name = next(n for n in z.namelist() if n.endswith('.csv'))
                for f in pd.read_csv(z.open(name), sep=';', encoding='utf-8-sig', usecols=COLS, chunksize=100_000):
                    evaluated = f['Avaliação Reclamação'].isin(['Resolvida', 'Não Resolvida'])
                    t = pd.to_numeric(f['Tempo Resposta'], errors='coerce')
                    eligible = (evaluated & f['Respondida'].eq('S') & t.ge(0) & np.isfinite(t)
                                & f['Nome Fantasia'].notna() & f['Grupo Problema'].notna())
                    cls.counts['total'] += len(f)
                    cls.counts['evaluated'] += int(evaluated.sum())
                    cls.counts['unresolved'] += int(f['Avaliação Reclamação'].eq('Não Resolvida').sum())
                    cls.counts['analytic'] += int(eligible.sum())
                    f = f.loc[eligible].assign(slow=t[eligible] > 7, y=f['Avaliação Reclamação'].eq('Não Resolvida'))
                    for key, n in f.groupby(['Nome Fantasia', 'Grupo Problema', 'slow', 'y']).size().items():
                        cls.tables[key] += int(n)
        metrics = json.loads((ROOT / 'reports/metrics.json').read_text(encoding='utf-8'))
        cls.quality, cls.primary = metrics['quality'], metrics['primary']

    def test_counts_match_published_metrics(self):
        self.assertEqual(self.counts['total'], self.quality['total_rows'])
        self.assertEqual(self.counts['evaluated'], self.quality['evaluated_rows'])
        self.assertEqual(self.counts['unresolved'], self.quality['unresolved_evaluated_rows'])
        self.assertEqual(self.counts['analytic'], self.quality['analytic_rows'])

    def test_effect_and_null_spread_match(self):
        included = strata = 0
        total = variance = 0.
        companies = set()
        for company, problem in sorted({k[:2] for k in self.tables}):
            y0, y1 = self.tables[(company, problem, False, True)], self.tables[(company, problem, True, True)]
            n0 = y0 + self.tables[(company, problem, False, False)]
            n1 = y1 + self.tables[(company, problem, True, False)]
            if n0 == 0 or n1 == 0:
                continue
            n, k = n0 + n1, y0 + y1
            included += n
            strata += 1
            companies.add(company)
            total += n * (y1 / n1 - y0 / n0)
            # Analytic hypergeometric variance of the weighted conditional difference.
            variance += n * n * k * (n - k) / (n0 * n1 * (n - 1))
        self.assertEqual(included, self.primary['included_rows'])
        self.assertEqual(strata, self.primary['eligible_strata'])
        self.assertEqual(len(companies), self.primary['companies_in_bootstrap'])
        self.assertAlmostEqual(total / included * 100, self.primary['effect_pp'], places=10)
        exact_sd = math.sqrt(variance) / included * 100
        self.assertLess(abs(self.primary['null_sd_pp'] / exact_sd - 1), .03)

    def test_p_value_matches_saved_null(self):
        null = pd.read_csv(ROOT / 'data/processed/permutation_null.csv').iloc[:, 0]
        self.assertEqual(len(null), self.primary['permutations'])
        extremes = int((null >= self.primary['effect_pp'] - 1e-12).sum())
        self.assertEqual(extremes, self.primary['extreme_count'])
        self.assertEqual((extremes + 1) / (len(null) + 1), self.primary['p_value'])


if __name__ == '__main__':
    unittest.main()
