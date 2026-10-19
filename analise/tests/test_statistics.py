"""Independent checks against enumerated small-sample reference distributions."""
from collections import Counter
from itertools import combinations, product
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atendimento.stats import cluster_bootstrap, make_strata, p_value, permutation_distribution


class PermutationDesignTests(unittest.TestCase):
    def setUp(self):
        # Deliberately unequal stratum sizes and very different base rates.
        rows = [
            ('A', 'billing', 1, 0), ('A', 'billing', 7, 0), ('A', 'billing', 8, 1),
            ('B', 'quality', 0, 1), ('B', 'quality', 4, 0), ('B', 'quality', 9, 1),
            ('B', 'quality', 10, 1), ('B', 'quality', 11, 1),
            ('C', 'quality', 1, 0), ('C', 'quality', 2, 1),  # No overlap: exclude.
        ]
        self.df = pd.DataFrame(rows, columns=['company', 'problem_group', 'days', 'unresolved'])
        self.tab, self.coverage = make_strata(self.df)

    def test_threshold_overlap_and_estimand(self):
        self.assertEqual(self.coverage['included_rows'], 8)
        self.assertEqual(self.coverage['excluded_rows'], 2)
        self.assertEqual(self.coverage['eligible_strata'], 2)
        self.assertEqual(self.coverage['excluded_strata'], 1)
        self.assertEqual(self.tab['n0'].tolist(), [2, 2])  # Day 7 belongs to fast.
        self.assertEqual(self.tab['n1'].tolist(), [1, 3])
        self.assertAlmostEqual(self.tab['contribution'].sum() / self.tab['n'].sum(), .6875)

    def test_constrained_distribution_against_all_label_permutations(self):
        # Enumerate all locations of unresolved labels separately within each block.
        block_values = []
        for row in self.tab.itertuples():
            values = []
            for unresolved_positions in combinations(range(row.n), row.y0 + row.y1):
                slow_successes = sum(i < row.n1 for i in unresolved_positions)
                fast_successes = row.y0 + row.y1 - slow_successes
                values.append(row.n * (slow_successes / row.n1 - fast_successes / row.n0) / 8)
            block_values.append(values)
        exact = np.array([sum(v) for v in product(*block_values)])
        expected = Counter(np.round(exact, 10))
        sampled = permutation_distribution(self.tab, permutations=40000, seed=713)
        actual = Counter(np.round(sampled, 10))
        self.assertEqual(set(actual), set(expected))
        for value, count in expected.items():
            self.assertAlmostEqual(actual[value] / len(sampled), count / len(exact), delta=.012)
        self.assertAlmostEqual(sampled.mean(), exact.mean(), delta=.007)
        self.assertAlmostEqual(sampled.var(), exact.var(), delta=.004)

    def test_seed_is_reproducible_and_all_equal_outcomes_are_null(self):
        np.testing.assert_array_equal(permutation_distribution(self.tab, 321, 7), permutation_distribution(self.tab, 321, 7))
        all_resolved = self.df.assign(unresolved=0)
        tab, _ = make_strata(all_resolved)
        np.testing.assert_array_equal(permutation_distribution(tab, 20, 5), np.zeros(20))

    def test_p_value_uses_monte_carlo_correction(self):
        null = np.array([0., .1, .2, .5])
        self.assertEqual(p_value(null, .2), (3 / 5, 2))  # Ties count as extreme.
        self.assertEqual(p_value(null, 9.), (1 / 5, 0))  # Never exactly zero.

    def test_bootstrap_keeps_whole_companies_and_ratio_estimand(self):
        # Three strata but only two independent company resampling units.
        tab = pd.DataFrame({'company': ['A', 'A', 'B'], 'n': [10, 30, 10],
                            'contribution': [5., 15., -5.]})
        ci, count = cluster_bootstrap(tab, replicates=4999, seed=19)
        # Resample two companies: AA=.5, AB=.3, BB=-.5; each extreme has P=.25.
        self.assertEqual(count, 2)
        np.testing.assert_allclose(ci, [-50., 50.])
        # One company with unequal strata must produce its pooled ratio, not
        # the unweighted average of the three stratum effects.
        one_company = tab.assign(company='A')
        ci, count = cluster_bootstrap(one_company, replicates=50, seed=19)
        self.assertEqual(count, 1)
        np.testing.assert_allclose(ci, [30., 30.])


if __name__ == '__main__':
    unittest.main()
