"""Pilot analysis on CSVs shaped like the ticket system export."""
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atendimento import piloto


def _csv(rows: list[tuple[str, str, str, int]]) -> str:
    """rows: (fila, status, sla_primeira_resposta, reaberturas)."""
    df = pd.DataFrame(rows, columns=['fila', 'status', 'sla_primeira_resposta', 'reaberturas'])
    handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, encoding='utf-8')
    df.to_csv(handle, index=False)
    handle.close()
    return handle.name


class PilotTests(unittest.TestCase):
    def test_strong_association_is_detected(self):
        rows = []
        for fila in ('Cobrança', 'Entrega'):
            rows += [(fila, 'fechado', 'violado', 1)] * 30 + [(fila, 'fechado', 'violado', 0)] * 10
            rows += [(fila, 'fechado', 'cumprido', 1)] * 5 + [(fila, 'fechado', 'cumprido', 0)] * 35
        result = piloto.run(_csv(rows), permutations=999)
        self.assertEqual(result['tickets_compared'], 160)
        self.assertAlmostEqual(result['effect_pp'], 62.5)            # 75% vs 12.5% in each queue
        self.assertEqual(result['p_value'], 1 / 1000)
        self.assertTrue(result['reject_h0'])

    def test_no_association_is_not_rejected(self):
        rows = [('Cobrança', 'fechado', s, r) for s in ('violado', 'cumprido') for r in (0, 1) for _ in range(20)]
        result = piloto.run(_csv(rows), permutations=999)
        self.assertAlmostEqual(result['effect_pp'], 0)
        self.assertFalse(result['reject_h0'])

    def test_only_tickets_with_a_proposal_count(self):
        rows = [('Cobrança', 'fechado', 'violado', 1), ('Cobrança', 'resolvido', 'cumprido', 0),
                ('Cobrança', 'em_atendimento', 'violado', 1),        # reopened: had a proposal, counts
                ('Cobrança', 'aberto', 'vencido', 0)]                 # never got a proposal: excluded
        self.assertEqual(len(piloto.load(_csv(rows))), 3)

    def test_needs_both_groups_in_some_queue(self):
        with self.assertRaises(ValueError):
            piloto.run(_csv([('Cobrança', 'fechado', 'cumprido', 0), ('Entrega', 'fechado', 'violado', 1)]))

    def test_rejects_files_that_are_not_the_export(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, encoding='utf-8')
        handle.write('a,b\n1,2\n')
        handle.close()
        with self.assertRaises(ValueError):
            piloto.load(handle.name)


if __name__ == '__main__':
    unittest.main()
