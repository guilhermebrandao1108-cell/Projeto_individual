"""Estudo de caso: tempo de resposta e não resolução no Consumidor.gov.br (2025).

Módulos:
    config    caminhos, sementes e parâmetros fixados no plano de análise
    download  coleta dos arquivos oficiais com verificação de SHA-256
    data      leitura, validação e amostra analítica
    describe  indicadores de qualidade e agregados descritivos
    stats     estratos, teste de permutação e bootstrap por empresas
    plots     gráficos em matplotlib (uma função por figura)
    pipeline  orquestra tudo e grava métricas, agregados e figuras
"""
