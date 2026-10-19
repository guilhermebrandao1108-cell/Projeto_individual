# Etapa 2 — Sistema de gestão de chamados

API REST em **FastAPI** e interface em **React + TypeScript**, com regras de negócio derivadas do [estudo de caso](../analise/).

| Parte | Pasta | Status |
|---|---|---|
| API (backend) | [`backend/`](backend/) | ✅ 85 testes (pytest), em SQLite e PostgreSQL 17 · migrações Alembic |
| Interface (frontend) | [`frontend/`](frontend/) | ✅ 18 testes (Vitest) + 9 de ponta a ponta (Playwright) |
| Integração contínua | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | ✅ análise + backend + frontend a cada push |

| Fila da equipe | Painel do gestor |
|---|---|
| ![Fila de atendimento ordenada por prazo, com SLA vencido em vermelho](docs/screenshots/fila.png) | ![Painel com SLA, solução confirmada, reabertura e avaliação](docs/screenshots/painel.png) |
| **Atendente propõe a solução** | **Só o cliente encerra** |
| ![Chamado com nota interna e solução proposta](docs/screenshots/chamado_atendente.png) | ![Cliente confirma a solução e avalia com 5 estrelas](docs/screenshots/confirmacao_cliente.png) |

## Da análise para o código

| Evidência do estudo | Regra implementada | Onde |
|---|---|---|
| +4,83 pp de não resolução acima de 7 dias | SLA de primeira resposta e de resolução **por fila**, com estado `em_risco` antes de vencer e **aviso por e-mail** ao responsável. O prazo de resolução **pausa enquanto o chamado aguarda o cliente**, mas a pausa nunca apaga um atraso que já aconteceu | [`domain/sla.py`](backend/app/domain/sla.py) |
| Responder ≠ resolver (respostas em 0–2 dias também falham) | A equipe só **propõe** a solução (`resolvido`). O chamado só fecha quando o **cliente confirma**, e se ele rejeitar, o chamado reabre | [`domain/workflow.py`](backend/app/domain/workflow.py) |
| 77,7% já tinham procurado a empresa | Histórico único: mensagens, notas internas e trilha de auditoria de cada evento | [`models.py`](backend/app/models.py) |
| Desempenho varia por empresa e problema | Filas (categorias), responsável, contagem de transferências e fila ordenada pelo prazo | [`services/tickets.py`](backend/app/services/tickets.py) |
| 67% sem avaliação | Avaliação de 1 a 5 na confirmação, com cobertura medida | [`services/metrics.py`](backend/app/services/metrics.py) |
| O piloto precisa de dados para o teste estatístico | `GET /metrics/export.csv` alimenta `python -m atendimento piloto` ([`analise/`](../analise/README.md#do-estudo-ao-piloto)): o mesmo teste de permutação da Etapa 1, agora sobre os chamados do sistema | [`services/export.py`](backend/app/services/export.py) |
| O piloto precisa de métricas | `GET /metrics/overview?start=&end=`: % no SLA, p90 da primeira resposta, solução confirmada, reabertura e cobertura de avaliação. O painel compara o período escolhido (7, 30 ou 90 dias) com o período anterior de mesmo tamanho | [`services/metrics.py`](backend/app/services/metrics.py) |

## Fluxo de um chamado

```
ABERTO ──primeira resposta / iniciar──▶ EM_ATENDIMENTO ◀──cliente responde── AGUARDANDO_CLIENTE
   │                                      │   ▲   └──────pedir_info──────────────────▶ │
   │                                      │   └──────rejeitar (reabre)──┐              │
   └──────────propor_solucao──────────────┴──────propor_solucao──▶ RESOLVIDO ◀─────────┘
                                                                       │ cliente confirma (+ nota 1–5)
                                                                       ▼
                                                                    FECHADO
```

| Perfil | Pode |
|---|---|
| **cliente** | abrir chamados; ver só os próprios; responder; confirmar ou rejeitar a solução; avaliar |
| **atendente** | ver a fila inteira; responder; escrever notas internas; iniciar; pedir informações; propor solução; assumir chamados sem responsável |
| **gestor** | tudo do atendente, mais transferir chamados, configurar filas e SLA, gerenciar a equipe, ver métricas e exportar dados |

Clientes recebem 404, e não 403, ao tentar acessar chamados de outra pessoa, para não revelar quais IDs existem. A equipe não consegue fechar um chamado em nome do cliente.

**Equipe:** quem é desativado não consegue mais entrar, e os chamados abertos dessa pessoa voltam para a fila sem responsável, com registro na auditoria. O gestor não pode desativar nem rebaixar a própria conta, então o sistema nunca fica sem gestor. A lista de usuários mostra só a equipe, e os e-mails dos clientes não aparecem para os atendentes.

**Login protegido contra força bruta:** depois de 5 senhas erradas em 15 minutos para a mesma conta e o mesmo IP, o login responde 429 com `Retry-After`, mesmo que a senha seguinte esteja certa. E-mail inexistente e senha errada recebem a mesma mensagem, no mesmo tempo, para não revelar quais contas existem ([`ratelimit.py`](backend/app/ratelimit.py)). Como o contador fica na memória, ele vale para uma instância só; com várias instâncias, iria para o Redis.

## Arquitetura do backend

O frontend tem a própria documentação em [`frontend/README.md`](frontend/README.md).

```
backend/app/
├── domain/            regras puras, sem banco e sem HTTP (testadas isoladamente)
│   ├── workflow.py    máquina de estados: ação × status × perfil → novo status
│   └── sla.py         prazos, pausa e estado do SLA (no_prazo, em_risco, vencido, pausado, cumprido, violado)
├── services/          casos de uso: aplicam o domínio, gravam no banco e registram auditoria
│   ├── tickets.py
│   └── metrics.py
├── routers/           camada HTTP fina: valida entrada, chama o serviço, serializa a saída
├── models.py          tabelas (SQLAlchemy 2)
├── schemas.py         contrato da API (Pydantic)
├── serializers.py     ORM → API, com campos calculados (SLA, ações permitidas, visibilidade)
├── deps.py            sessão, usuário logado, perfis e relógio injetável
├── security.py        hash scrypt e JWT
├── migrate.py         Alembic programático (usado pelo seed e pelos testes)
├── mailer.py          envio de e-mail (terminal em dev, SMTP em produção)
├── notify.py          comando dos avisos de prazo
└── seed.py            dados de demonstração gerados pelos próprios serviços
backend/migrations/versions/
├── 0001_esquema_inicial.py
├── 0002_pausa_do_sla_aguardando_cliente.py
├── 0003_pontos_de_risco_do_sla.py   migração de dados: preenche os chamados existentes
└── 0004_avisos_de_prazo.py
```

As dependências vão sempre para dentro: `routers → services → domain`. O domínio não conhece o banco nem o FastAPI. O relógio (`get_now`) é uma dependência injetável, e é isso que permite testar regras de SLA avançando o tempo, sem `sleep`.

Os erros de regra viram respostas HTTP num lugar só ([`main.py`](backend/app/main.py)): `DomainError` vira 409, `PermissionDenied` vira 403 e `NotFound` vira 404.

**Migrações:** o esquema é versionado com Alembic, e a aplicação nunca cria tabelas sozinha. Todas as restrições têm nome (via `naming_convention`), o que torna as migrações reprodutíveis no SQLite e no PostgreSQL. O teste [`test_migrations.py`](backend/tests/test_migrations.py) garante três coisas: aplicar todas as migrações gera exatamente o esquema dos modelos, o `downgrade` volta a um banco vazio e a migração da pausa preserva os chamados existentes.

## Como executar

Requer Python 3.11+ e Node.js 20+. São dois terminais.

**1. API**, na pasta `sistema/backend/`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed --reset        # aplica as migrações e cria dados de demonstração (senha: demo12345)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**2. Interface**, na pasta `sistema/frontend/`:

```powershell
npm install
npm run dev
```

Para começar com um banco vazio, sem dados de demonstração, use `.\.venv\Scripts\alembic.exe upgrade head`. Depois de mudar um modelo, gere a migração com `alembic revision --autogenerate -m "descrição"` e revise o arquivo gerado.

Abra http://localhost:5173 e use os botões **Cliente**, **Atendente** ou **Gestor** na tela de login. As contas de demonstração são `ana@demo.com`, `lucas@demo.com` e `gestor@demo.com`, todas com a senha `demo12345`. A documentação interativa da API fica em http://localhost:8000/docs.

```powershell
.\.venv\Scripts\python.exe -m pytest        # backend: 85 testes, ~25 s
npm test                                     # frontend (em sistema/frontend): 18 testes
npm run e2e                                  # ponta a ponta: sobe API + interface e roda 9 fluxos no navegador
```

**PostgreSQL:** a aplicação e as migrações funcionam igualmente em SQLite (desenvolvimento) e PostgreSQL (produção). Para testar contra um servidor real:

```powershell
# qualquer PostgreSQL 15+; por exemplo: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:17
$env:TEST_DATABASE_URL = 'postgresql+psycopg://postgres:postgres@localhost:5432/postgres'
.\.venv\Scripts\python.exe -m pytest
```

O CI ([`ci.yml`](../.github/workflows/ci.yml)) roda a cada push os testes da análise, as migrações (`alembic upgrade head` + `alembic check`), os testes e o seed do backend, em SQLite e num PostgreSQL 17 de verdade, o lint, os testes e o build do frontend e, por último, os testes de ponta a ponta no Chromium.

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./chamados.db` | PostgreSQL: `postgresql+psycopg://usuario:senha@host:5432/banco` (driver já incluso) |
| `TEST_DATABASE_URL` | vazio (SQLite em memória) | Roda os testes num servidor real; cada teste recria o esquema, então use um banco descartável |
| `SECRET_KEY` | chave de desenvolvimento (com aviso) | Obrigatória em produção |
| `TOKEN_MINUTES` | `480` | Validade do token |
| `CORS_ORIGINS` | `http://localhost:5173` | Origem do frontend (Vite) |
| `SLA_RISK_FRACTION` | `0.8` | A partir de quanto do prazo o chamado fica "em risco" |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | vazio (imprime no terminal) | Envio dos avisos de prazo por SMTP com STARTTLS |
| `APP_URL` | `http://localhost:5173` | Endereço da interface, usado nos links dos e-mails |

## Avisos de prazo por e-mail

`python -m app.notify` envia um e-mail quando um prazo de primeira resposta ou de resolução entra **em risco** (a partir de 80% da janela) e outro quando **vence**. O aviso vai para o responsável; chamados sem responsável, ou com responsável desativado, avisam os gestores. Cada aviso fica registrado na tabela `notifications`, com uma chave única por chamado, tipo, prazo e destinatário. Por isso, o comando pode rodar quantas vezes for preciso sem repetir e-mails. Se uma pausa mover o prazo, o novo prazo pode gerar um novo aviso. Prazos pausados, já cumpridos ou de chamados fechados não geram aviso ([`services/notifications.py`](backend/app/services/notifications.py)).

```powershell
.\.venv\Scripts\python.exe -m app.notify              # uma verificação (agende a cada 5 min)
.\.venv\Scripts\python.exe -m app.notify --every 300  # ou deixe rodando
```

Sem `SMTP_HOST`, os e-mails são impressos no terminal, o que serve para desenvolvimento. Para agendar no Windows, use `schtasks /create /sc minute /mo 5 /tn ChamadosAvisos /tr "<caminho>\.venv\Scripts\python.exe -m app.notify"`; no Linux, use uma linha no `cron`.

## Endpoints

| Método | Rota | Quem |
|---|---|---|
| POST | `/auth/register`, `/auth/token` · GET `/auth/me` | público / logado |
| GET | `/tickets?status=&open_only=&category_id=&assignee_id=&unassigned=&sla=&q=&limit=&offset=` → `{items, total, open_at_risk, open_overdue}` | todos (cliente vê só os próprios) |
| POST | `/tickets` | cliente |
| GET | `/tickets/{id}` | dono ou equipe |
| POST | `/tickets/{id}/messages` | dono ou equipe (`internal` só para a equipe) |
| POST | `/tickets/{id}/actions` (`iniciar`, `pedir_info`) · `/resolve` | equipe |
| POST | `/tickets/{id}/confirm` · `/reject` | cliente dono |
| POST | `/tickets/{id}/assign` | atendente (assumir) / gestor (transferir) |
| GET, POST, PATCH | `/categories` | leitura: todos · escrita: gestor |
| GET, POST | `/users` (só a equipe: clientes nunca são listados) | equipe / gestor |
| PATCH | `/users/{id}` (`is_active`, `role`): desativar devolve os chamados abertos à fila | gestor |
| GET | `/metrics/overview?start=&end=&category_id=` | gestor |
| GET | `/metrics/export.csv?start=&end=`: um chamado por linha, sem nomes, e-mails ou mensagens | gestor |

## Decisões e próximos passos

- **O SLA de resolução pausa enquanto o chamado aguarda o cliente.** Quando o cliente responde, o prazo avança pelo tempo de espera, e o total fica registrado em `sla_paused_seconds`. Se o prazo já tinha vencido quando a pausa começou, o chamado continua vencido. A primeira resposta não pausa, porque pedir informação já conta como resposta.
- **Uma mudança de SLA não altera chamados já abertos.** O prazo combinado na abertura é mantido, e há um teste que garante isso.
- **O SLA de resolução conta a proposta de solução,** não a confirmação. Se o cliente rejeitar, a proposta deixa de valer e o prazo continua correndo.
- **A fila é filtrada, ordenada, contada e paginada no banco.** Para isso, cada prazo guarda também o seu *ponto de risco* (`*_risk_at`, 80% da janela). Assim, todos os estados de SLA viram comparações simples de data, iguais no Python (`domain/sla.state`) e no SQL (`services/tickets.sla_condition`), com índice nas colunas de prazo. O teste [`test_queue.py`](backend/tests/test_queue.py) verifica, chamado por chamado e em vários instantes, que as duas versões classificam tudo igual. A migração 0003 calcula o ponto de risco dos chamados que já existiam.
- **Próximos passos:** agregações do painel em SQL (hoje calculadas em Python) e anexos nos chamados.
