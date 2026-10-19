# Frontend — React + TypeScript

Interface do sistema de chamados, com uma tela para cada perfil: cliente, atendente e gestor. Consome a API em [`../backend`](../backend).

## Stack

- **React 19 + TypeScript + Vite**
- **React Router**: rotas com guarda por perfil (`RequireAuth`)
- **TanStack Query**: estado do servidor, cache, revalidação após cada ação e atualização periódica da fila para manter o SLA em dia
- **CSS próprio com tokens**, sem biblioteca de componentes, responsivo até 390 px
- **Vitest + Testing Library**: testes de formatação e componentes
- **Playwright**: testes de ponta a ponta com a API real e um banco recriado a cada execução

## Estrutura

```
src/
├── api/
│   ├── types.ts        espelho do contrato da API (backend/app/schemas.py)
│   ├── client.ts       fetch com token, erros da API → ApiError, logout automático no 401
│   └── hooks.ts        uma query/mutation por endpoint; nenhum componente chama fetch direto
├── auth/               contexto de sessão (login, cadastro, logout)
├── components/         Layout e guardas de rota, badges de status/SLA, nota de 1 a 5
├── pages/
│   ├── Customer.tsx    meus chamados e abrir chamado
│   ├── Queue.tsx       fila da equipe com filtros e atalhos para vencidos e em risco
│   ├── TicketPage.tsx  conversa, notas internas, ações, confirmação pelo cliente
│   └── Manager.tsx     painel de métricas, filas/SLA e equipe
└── lib/format.ts       rótulos e datas em pt-BR
e2e/
├── chamados.spec.ts    fluxos completos no navegador (desktop e celular)
└── helpers.ts          login pelos atalhos de demonstração e falha em erro de console
```

**A interface não decide regras.** As ações que aparecem num chamado vêm de `allowed_actions`, calculado pelo backend a partir do status e do perfil. Se a regra mudar no servidor, a tela acompanha.

## Executar

Com a API rodando em `localhost:8000` (veja [`../backend`](../README.md#como-executar)):

```powershell
npm install
npm run dev        # http://localhost:5173
```

Em desenvolvimento, o Vite encaminha `/api/*` para a API, então não há URL do backend fixada no código. Para apontar para outro endereço, use `API_URL=http://... npm run dev`. A tela de login mostra atalhos para as contas de demonstração, mas só no modo de desenvolvimento.

```powershell
npm test           # Vitest
npm run lint       # oxlint
npm run build      # checagem de tipos + build de produção em dist/
npm run e2e        # Playwright: sobe API (porta 8001) e Vite (5174) e roda 9 fluxos
```

O `npm run e2e` não usa o banco nem os servidores de desenvolvimento. Ele recria um banco próprio (`backend/e2e.db`) com os dados de demonstração e sobe a API e o Vite em portas separadas. No Windows, usa o Edge já instalado. Em outros sistemas, rode `npx playwright install chromium` uma vez antes. Os testes cobrem:

- o ciclo completo, em que a nota interna não aparece para o cliente e só ele encerra o chamado;
- a rejeição da solução, que reabre o chamado;
- a pausa do SLA ao pedir informações;
- o acesso por perfil e o redirecionamento de quem não está logado;
- o painel do gestor;
- a paginação da fila, feita no servidor;
- a exportação do CSV, sem dados pessoais;
- a desativação de um atendente, que devolve os chamados dele à fila;
- a fila no celular sem rolagem horizontal.

Qualquer erro no console do navegador faz o teste falhar.
