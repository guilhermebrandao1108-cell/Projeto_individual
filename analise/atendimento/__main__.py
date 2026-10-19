"""CLI: python -m atendimento {baixar,analisar,piloto} (run from the analise/ folder)."""
import argparse

import matplotlib
matplotlib.use('Agg')  # headless: figures are only written to disk

from . import download, pipeline, piloto  # noqa: E402
from .config import PERMUTATIONS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(prog='python -m atendimento', description='Estudo de caso Consumidor.gov.br 2025')
    commands = parser.add_subparsers(dest='command', required=True)
    baixar = commands.add_parser('baixar', help='baixa e verifica os 12 arquivos oficiais de 2025')
    baixar.add_argument('--refresh-manifest', action='store_true',
                        help='redescobre o catálogo oficial e regrava o manifesto; revise o diff antes de atualizar resultados')
    commands.add_parser('analisar', help='executa a análise e regenera métricas, agregados e figuras')
    pilot = commands.add_parser('piloto', help='aplica o teste de permutação aos chamados exportados pelo sistema')
    pilot.add_argument('csv', help='arquivo de GET /metrics/export.csv')
    pilot.add_argument('--permutacoes', type=int, default=PERMUTATIONS)
    args = parser.parse_args()
    if args.command == 'baixar':
        download.run(refresh_manifest=args.refresh_manifest)
    elif args.command == 'piloto':
        print(piloto.report(piloto.run(args.csv, permutations=args.permutacoes)))
    else:
        pipeline.run()


if __name__ == '__main__':
    main()
