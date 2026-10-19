"""Demo data: `python -m app.seed [--reset]`.

Tickets are created through the same services as the API, moving the clock back in time,
so every record respects the workflow rules and the audit trail is realistic.
"""
import argparse
import random
from datetime import timedelta

from sqlalchemy import func, select, text

from . import migrate
from .database import Base, SessionLocal, engine
from .domain.workflow import Action
from .models import Category, Priority, Role, User
from .security import hash_password
from .services import tickets as svc
from .timeutils import utcnow

PASSWORD = 'demo12345'
CATEGORIES = [('Acesso à conta', 2, 24), ('Cobrança', 4, 48), ('Entrega', 8, 72), ('Produto com defeito', 8, 120)]
STAFF = [('Gabriela Gestora', 'gestor@demo.com', Role.GESTOR),
         ('Lucas Atendente', 'lucas@demo.com', Role.ATENDENTE),
         ('Marina Atendente', 'marina@demo.com', Role.ATENDENTE)]
CUSTOMERS = [('Ana Souza', 'ana@demo.com'), ('Bruno Lima', 'bruno@demo.com'), ('Carla Dias', 'carla@demo.com'),
             ('Diego Rocha', 'diego@demo.com'), ('Elisa Martins', 'elisa@demo.com')]
PROBLEMS = {
    'Acesso à conta': [('Não consigo entrar no aplicativo', 'Digito a senha certa e aparece "credenciais inválidas".'),
                       ('Código de verificação não chega', 'Peço o código por SMS e nunca recebo.')],
    'Cobrança': [('Cobrança em duplicidade', 'Fui cobrado duas vezes pela mesma compra no cartão.'),
                 ('Valor diferente do contratado', 'A fatura veio com um valor maior que o do plano.')],
    'Entrega': [('Pedido atrasado', 'O prazo de entrega venceu e o rastreio não atualiza há dias.'),
                ('Entregue no endereço errado', 'O rastreio diz entregue, mas não recebi nada.')],
    'Produto com defeito': [('Produto chegou quebrado', 'A tela do aparelho veio trincada na caixa.'),
                            ('Parou de funcionar em uma semana', 'O equipamento não liga mais desde ontem.')],
}


def seed(reset: bool) -> None:
    if reset:
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
    with engine.begin() as conn:
        migrate.upgrade(conn)
    rng = random.Random(2026)
    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))):
            raise SystemExit('O banco já tem dados. Use --reset para recriá-lo.')
        categories = [Category(name=n, first_response_hours=f, resolution_hours=r) for n, f, r in CATEGORIES]
        staff = [User(name=n, email=e, role=role) for n, e, role in STAFF]
        customers = [User(name=n, email=e, role=Role.CLIENTE) for n, e in CUSTOMERS]
        for user in staff + customers:
            user.password_hash = hash_password(PASSWORD)
        db.add_all(categories + staff + customers)
        db.commit()
        agents = [u for u in staff if u.role == Role.ATENDENTE]
        manager = staff[0]

        now = utcnow()
        for i in range(40):
            category = rng.choice(categories)
            title, description = rng.choice(PROBLEMS[category.name])
            outcome = rng.random()
            # Finished tickets spread over two weeks; tickets still in progress are recent, so the queue shows a
            # realistic mix of on-time, at-risk and overdue items instead of everything being late.
            window = category.first_response_hours if outcome < .12 else category.resolution_hours
            age = timedelta(days=rng.uniform(1, 14)) if outcome >= .5 else timedelta(hours=rng.uniform(.1, 1.2) * window)
            clock = now - age
            t = svc.create_ticket(db, rng.choice(customers), title=title, description=description, category_id=category.id,
                                  priority=rng.choices(list(Priority), weights=[2, 5, 2, 1])[0], now=clock)
            if outcome < .12:          # still waiting for a first reply (some overdue, some at risk)
                continue
            agent = rng.choice(agents)
            # Some replies are late on purpose: the queue must show SLA breaches.
            clock += timedelta(hours=rng.uniform(.2, 1.6) * category.first_response_hours)
            if clock > now:
                continue
            svc.assign(db, manager, t, assignee_id=agent.id, now=clock)
            svc.add_message(db, agent, t, body='Olá! Recebemos seu chamado e já estamos verificando.', internal=False, now=clock)
            if outcome < .25:          # in progress
                continue
            if outcome < .35:          # waiting for the customer
                svc.apply_action(db, agent, t, action=Action.PEDIR_INFO, message='Pode enviar o número do pedido?', now=clock)
                continue
            clock += timedelta(hours=rng.uniform(.1, .9) * category.resolution_hours)
            if clock > now:
                continue
            svc.propose_resolution(db, agent, t, message='Ajustamos o problema. Pode confirmar se está tudo certo?', now=clock)
            if outcome < .5:           # waiting for confirmation
                continue
            clock += timedelta(hours=rng.uniform(1, 24))
            if clock > now:
                continue
            if outcome < .62:          # rejected: reopened
                svc.reject_resolution(db, t.customer, t, message='Ainda não funcionou, continuo com o problema.', now=clock)
                continue
            rating = rng.choices([5, 4, 3, 2, 1, None], weights=[30, 25, 10, 5, 5, 25])[0]
            svc.confirm_resolution(db, t.customer, t, satisfaction=rating, comment=None, now=clock)
    print(f'Dados de demonstração criados. Senha de todos os usuários: {PASSWORD}')
    for name, email, role in STAFF:
        print(f'  {role:<9} {email}')
    print(f'  cliente   {CUSTOMERS[0][1]} (e outros {len(CUSTOMERS) - 1})')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--reset', action='store_true', help='apaga e recria todas as tabelas')
    seed(parser.parse_args().reset)
