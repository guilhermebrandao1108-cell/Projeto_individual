# Etapa 1 — Estudo de caso: tempo de resposta e não resolução

Esta etapa usa dados públicos para verificar se a dor existe antes de construir o sistema de gestão de chamados. Ela entrega uma pesquisa reproduzível e a análise estatística.

**Comece pelo [notebook](notebooks/estudo.ipynb).** Ele carrega os dados oficiais, roda cada etapa chamando o pacote `atendimento/` e mostra o código do teste e os gráficos inline. No final, confere que os números batem com `reports/metrics.json`. Também disponíveis: o [estudo de caso visual (HTML)](reports/estudo_de_caso.html) e o [relatório completo](reports/relatorio.md).

## Pergunta e resultado

Entre as reclamações finalizadas no Consumidor.gov.br em 2025 e avaliadas explicitamente, respostas com tempo oficial superior a sete dias estão associadas a mais casos não resolvidos? A comparação é feita dentro da mesma empresa e do mesmo grupo de problema.

| | |
|---|---|
| **H₀** | Dentro de cada estrato empresa × grupo de problema, os rótulos resolvida/não resolvida não dependem da faixa de tempo |
| **H₁** | A diferença ponderada de não resolução é positiva para respostas acima de 7 dias (unilateral, α = 5%) |
| **Teste** | 9.999 permutações condicionais em 4.121 estratos (741.423 reclamações de 1.054 empresas) |
| **Resultado** | **+4,83 pp**, IC95% por empresas de 2,43 a 6,99 pp, **p = 0,0001**, H₀ rejeitada |
| **Robustez** | Com corte de 5 ou 10 dias, ou estratos de segmento × problema, o efeito fica entre +3,58 e +4,83 pp |

![Distribuição nula da permutação e efeito observado](figures/05_permutacao_e_efeito.png)

O [plano analítico](docs/plano_analise.md) foi registrado localmente antes dos resultados, depois de inspecionar apenas o cabeçalho dos arquivos. Não é um pré-registro público independente.

## Estrutura

```
analise/
├── atendimento/          pacote Python com toda a lógica
│   ├── config.py         caminhos, sementes e parâmetros do plano (corte de 7 dias, B = 9.999...)
│   ├── download.py       coleta dos 12 ZIPs oficiais com verificação de SHA-256
│   ├── data.py           leitura, validação do esquema e amostra analítica
│   ├── describe.py       indicadores de qualidade e agregados descritivos
│   ├── stats.py          estratos, teste de permutação, p-valor e bootstrap por empresas
│   ├── plots.py          gráficos em matplotlib, uma função por figura
│   ├── pipeline.py       orquestra: dados → descrição → teste → métricas, CSVs e figuras
│   ├── piloto.py         o mesmo teste aplicado aos chamados exportados pelo sistema (Etapa 2)
│   └── __main__.py       linha de comando: baixar | analisar | piloto
├── tests/
│   ├── test_statistics.py  algoritmo comparado com a enumeração exata em amostra pequena
│   ├── test_auditoria.py   recálculo independente a partir dos dados brutos
│   └── test_piloto.py      análise do piloto com dados sintéticos de efeito conhecido
├── data/
│   ├── manifest.json     URLs oficiais, tamanhos e SHA-256 dos arquivos usados
│   ├── raw/              ZIPs oficiais (fora do Git, baixados pelo comando baixar)
│   └── processed/        apenas agregados e a distribuição nula
├── figures/              6 gráficos PNG gerados por plots.py
├── reports/              relatorio.md, estudo_de_caso.html, metrics.json
├── notebooks/estudo.ipynb  vitrine: roda a análise passo a passo usando o pacote
└── docs/plano_analise.md   hipótese, critérios e sensibilidades definidos antes dos resultados
```

O fluxo é linear e cada módulo depende só dos anteriores: `config → data → describe/stats → plots → pipeline`. A estatística (`stats.py`) não lê arquivos nem desenha gráficos, por isso é testada isoladamente. Os gráficos (`plots.py`) recebem tabelas já calculadas, salvam o PNG e devolvem a figura. É assim que o notebook os exibe inline.

O pacote e o notebook se dividem assim: o **pacote** guarda a lógica, que é testada e reutilizável pela linha de comando, e o **notebook** guarda a narrativa, chamando as mesmas funções em ordem e explicando cada resultado. Não há lógica duplicada entre os dois.

## Como executar

Requer Python 3.11 ou superior. A execução verificada usou Python 3.14 e as versões fixadas em `requirements.txt`. Os comandos abaixo são para Windows/PowerShell e devem ser rodados dentro da pasta `analise/`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m atendimento baixar      # ~77 MB da fonte oficial
.\.venv\Scripts\python.exe -m atendimento analisar    # ~1 min, regenera métricas, CSVs e figuras
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Em macOS/Linux, use `python3 -m venv .venv` e `.venv/bin/python`.

O comando `baixar` verifica cada arquivo contra o SHA-256 do manifesto e recusa versões diferentes do snapshot registrado. A opção `--refresh-manifest` redescobre o catálogo oficial e regrava o manifesto, então revise o diff antes de atualizar resultados. Sem os dados brutos, `test_auditoria.py` é pulado e os testes do algoritmo continuam rodando.

Para rodar o notebook, instale o Jupyter (`pip install jupyter`), baixe os dados e abra `notebooks/estudo.ipynb`. A execução completa leva cerca de 1 minuto.

## Do estudo ao piloto

O sistema da Etapa 2 exporta os seus chamados (`GET /metrics/export.csv`, ou o botão **Exportar CSV** no painel do gestor), com uma linha por chamado e sem dados pessoais. O mesmo teste de permutação roda sobre esse arquivo:

```powershell
py -m atendimento piloto chamados_20261018.csv
```

A pergunta é a mesma do estudo, adaptada aos dados do sistema: entre os chamados que receberam uma proposta de solução, os que tiveram a primeira resposta fora do SLA foram mais reabertos (solução rejeitada pelo cliente), comparando dentro da mesma fila? O teste usa as mesmas funções validadas em `tests/test_statistics.py`. Assim como no estudo, o resultado é uma associação. Para medir o efeito do sistema, é preciso comparar grupos com e sem ele (seção 5 do [relatório](reports/relatorio.md)).

## Dados, privacidade e limites

Fonte: [Consumidor.gov.br / Senacon](https://www.consumidor.gov.br/pages/dadosabertos/externo/), arquivos de reclamações **finalizadas** de janeiro a dezembro de 2025. O código lê apenas as colunas necessárias e não grava microdados nem dados pessoais nos resultados. A licença específica dos arquivos deve ser confirmada na fonte antes de redistribuí-los. Por isso, este repositório publica o downloader, o manifesto e apenas resultados agregados.

“Não avaliada” significa ausência de informação sobre a resolução, não sucesso. A taxa de não resolução entre avaliadas não é o inverso do índice oficial de solução. O tempo oficial de resposta desconta o período de análise do gestor ([dicionário da ANAC](https://www.anac.gov.br/acesso-a-informacao/dados-abertos/areas-de-atuacao/voos-e-operacoes-aereas/dados-do-consumidor-gov/52-dados-do-consumidor-gov)). O corte de sete dias é uma referência operacional, não um SLA oficial.

O estudo é observacional: mostra associação, não causa. A seleção de quem avalia (33%), a complexidade não medida dos casos e consumidores repetidos podem afetar o resultado. O teste exige permutabilidade dentro dos estratos, o que não é garantido sem randomização. A eficácia do sistema de chamados será avaliada em um piloto, descrito na seção 5 do [relatório](reports/relatorio.md).
