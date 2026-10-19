# Frontend — React + TypeScript

Interface do sistema de chamados, com uma tela para cada perfil: cliente, atendente e gestor. Consome a API em [`../backend`](../backend).

## Stack

- **React 19 + TypeScript + Vite**
- **React Router**: rotas com guarda por perfil (`RequireAuth`)
- **TanStack Query**: estado do servidor, cache, revalidação após cada ação e atualização periódica da fila para manter o SLA em dia
- **CSS próprio com tokens**, sem biblioteca de componentes, responsivo até 390 px
- **Vitest + Testing Library**: testes de formatação e componentes

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
```
