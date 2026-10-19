# Etapa 2 — Sistema de gestão de chamados

API REST em **FastAPI** e interface em **React + TypeScript**, com regras de negócio derivadas do [estudo de caso](../analise/).

| Parte | Pasta | Status |
|---|---|---|
| API (backend) | [`backend/`](backend/) | ✅ 61 testes (pytest) · migrações Alembic |
| Interface (frontend) | [`frontend/`](frontend/) | ✅ 13 testes (Vitest) + 7 de ponta a ponta (Playwright) |
| Integração contínua | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | ✅ análise + backend + frontend a cada push |

| Fila da equipe | Painel do gestor |
|---|---|
| ![Fila de atendimento ordenada por prazo, com SLA vencido em vermelho](docs/screenshots/fila.png) | ![Painel com SLA, solução confirmada, reabertura e avaliação](docs/screenshots/painel.png) |
| **Atendente propõe a solução** | **Só o cliente encerra** |
| ![Chamado com nota interna e solução proposta](docs/screenshots/chamado_atendente.png) | ![Cliente confirma a solução e avalia com 5 estrelas](docs/screenshots/confirmacao_cliente.png) |

## Da análise para o código

| Evidência do estudo | Regra implementada | Onde |
|---|---|---|
| +4,83 pp de não resolução acima de 7 dias | SLA de primeira resposta e de resolução **por fila**, com estado `em_risco` antes de vencer. O prazo de resolução **pausa enquanto o chamado aguarda o cliente**, mas a pausa nunca apaga um atraso que já aconteceu | [`domain/sla.py`](backend/app/domain/sla.py) |
| Responder ≠ resolver (respostas em 0–2 dias também falham) | A equipe só **propõe** a solução (`resolvido`). O chamado só fecha quando o **cliente confirma**, e se ele rejeitar, o chamado reabre | [`domain/workflow.py`](backend/app/domain/workflow.py) |
| 77,7% já tinham procurado a empresa | Histórico único: mensagens, notas internas e trilha de auditoria de cada evento | [`models.py`](backend/app/models.py) |
| Desempenho varia por empresa e problema | Filas (categorias), responsável, contagem de transferências e fila ordenada pelo prazo | [`services/tickets.py`](backend/app/services/tickets.py) |
| 67% sem avaliação | Avaliação de 1 a 5 na confirmação, com cobertura medida | [`services/metrics.py`](backend/app/services/metrics.py) |
| O piloto precisa de métricas | `GET /metrics/overview`: % no SLA, p90 da primeira resposta, solução confirmada, reabertura e cobertura de avaliação | [`services/metrics.py`](backend/app/services/metrics.py) |

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
| **gestor** | tudo do atendente, mais transferir chamados, configurar filas e SLA, criar usuários e ver métricas |

Clientes recebem 404, e não 403, ao tentar acessar chamados de outra pessoa, para não revelar quais IDs existem. A equipe não consegue fechar um chamado em nome do cliente.

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
└── seed.py            dados de demonstração gerados pelos próprios serviços
backend/migrations/versions/
├── 0001_esquema_inicial.py
└── 0002_pausa_do_sla_aguardando_cliente.py
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
.\.venv\Scripts\python.exe -m pytest        # backend: 61 testes, ~15 s
npm test                                     # frontend (em sistema/frontend): 13 testes
npm run e2e                                  # ponta a ponta: sobe API + interface e roda 7 fluxos no navegador
```

O CI ([`ci.yml`](../.github/workflows/ci.yml)) roda a cada push os testes da análise, as migrações (`alembic upgrade head` + `alembic check`), os testes e o seed do backend, o lint, os testes e o build do frontend e, por último, os testes de ponta a ponta no Chromium.

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./chamados.db` | Para PostgreSQL, use `postgresql+psycopg://...` e instale `psycopg` |
| `SECRET_KEY` | chave de desenvolvimento (com aviso) | Obrigatória em produção |
| `TOKEN_MINUTES` | `480` | Validade do token |
| `CORS_ORIGINS` | `http://localhost:5173` | Origem do frontend (Vite) |
| `SLA_RISK_FRACTION` | `0.8` | A partir de quanto do prazo o chamado fica "em risco" |

## Endpoints

| Método | Rota | Quem |
|---|---|---|
| POST | `/auth/register`, `/auth/token` · GET `/auth/me` | público / logado |
| GET | `/tickets?status=&category_id=&assignee_id=&unassigned=&sla=&q=` | todos (cliente vê só os próprios) |
| POST | `/tickets` | cliente |
| GET | `/tickets/{id}` | dono ou equipe |
| POST | `/tickets/{id}/messages` | dono ou equipe (`internal` só para a equipe) |
| POST | `/tickets/{id}/actions` (`iniciar`, `pedir_info`) · `/resolve` | equipe |
| POST | `/tickets/{id}/confirm` · `/reject` | cliente dono |
| POST | `/tickets/{id}/assign` | atendente (assumir) / gestor (transferir) |
| GET, POST, PATCH | `/categories` | leitura: todos · escrita: gestor |
| GET, POST | `/users` | equipe / gestor |
| GET | `/metrics/overview?start=&end=&category_id=` | gestor |

## Decisões e próximos passos

- **O SLA de resolução pausa enquanto o chamado aguarda o cliente.** Quando o cliente responde, o prazo avança pelo tempo de espera, e o total fica registrado em `sla_paused_seconds`. Se o prazo já tinha vencido quando a pausa começou, o chamado continua vencido. A primeira resposta não pausa, porque pedir informação já conta como resposta.
- **Uma mudança de SLA não altera chamados já abertos.** O prazo combinado na abertura é mantido, e há um teste que garante isso.
- **O SLA de resolução conta a proposta de solução,** não a confirmação. Se o cliente rejeitar, a proposta deixa de valer e o prazo continua correndo.
- **Na fila, o filtro por estado de SLA é calculado em Python.** Com volume real, ele vai para SQL, comparando `*_due_at` com `now` e com as colunas `*_at`.
- **Próximos passos:** PostgreSQL via Docker Compose (as migrações já são compatíveis), notificação por e-mail quando um chamado entra "em risco" e paginação da fila.
