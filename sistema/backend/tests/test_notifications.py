"""Deadline e-mails: who receives them, when, and never twice."""
from datetime import timedelta

from app.domain.workflow import Action
from app.mailer import Mail
from app.models import Category, Priority
from app.services import tickets as svc
from app.services.notifications import send_alerts


class FakeMailer:
    def __init__(self):
        self.sent: list[Mail] = []

    def send(self, mail: Mail) -> None:
        self.sent.append(mail)


def _setup(db, users, clock):
    queue = Category(name='Cobrança', first_response_hours=4, resolution_hours=10)
    db.add(queue)
    db.commit()
    new = lambda: svc.create_ticket(db, users['cliente'], title='Cobrança em duplicidade', description='Fui cobrado duas vezes.',
                                    category_id=queue.id, priority=Priority.ALTA, now=clock.now)
    return new


def test_owner_is_warned_before_the_deadline_and_only_once(db, users, clock):
    new = _setup(db, users, clock)
    t = new()
    svc.assign(db, users['gestor'], t, assignee_id=users['atendente'].id, now=clock.now)
    mailer = FakeMailer()

    assert send_alerts(db, mailer, clock.now) == 0                     # nothing yet
    clock.advance(hours=3, minutes=20)                                # 83% of the 4h window
    assert send_alerts(db, mailer, clock.now) == 1
    mail = mailer.sent[0]
    assert mail.to == users['atendente'].email
    assert mail.subject == f'[Chamado #{t.id}] Prazo de primeira resposta em risco'
    assert f'/chamados/{t.id}' in mail.body
    assert 'Prioridade: Alta' in mail.body
    assert send_alerts(db, mailer, clock.now) == 0                     # idempotent: no repeat

    clock.advance(hours=1)                                            # now overdue: a different alert
    assert send_alerts(db, mailer, clock.now) == 1
    assert mailer.sent[-1].subject.endswith('primeira resposta vencido')


def test_unowned_tickets_go_to_every_active_manager(db, users, clock):
    new = _setup(db, users, clock)
    new()
    clock.advance(hours=5)
    mailer = FakeMailer()
    send_alerts(db, mailer, clock.now)
    assert {m.to for m in mailer.sent} == {users['gestor'].email}


def test_met_paused_and_closed_targets_are_not_alerted(db, users, clock):
    new = _setup(db, users, clock)
    answered, paused, solved = new(), new(), new()
    agent = users['atendente']
    clock.advance(hours=1)
    svc.add_message(db, agent, answered, body='Olá', internal=False, now=clock.now)
    svc.apply_action(db, agent, paused, action=Action.INICIAR, message=None, now=clock.now)
    svc.apply_action(db, agent, paused, action=Action.PEDIR_INFO, message='Número do pedido?', now=clock.now)
    svc.propose_resolution(db, agent, solved, message='Feito.', now=clock.now)
    clock.advance(hours=8)                                             # 90% of the 10h resolution window
    mailer = FakeMailer()
    send_alerts(db, mailer, clock.now)
    alerted = {m.subject.split('#')[1].split(']')[0] for m in mailer.sent}
    assert alerted == {str(answered.id)}                               # paused and solved stay quiet


def test_a_deadline_moved_by_a_pause_can_be_alerted_again(db, users, clock):
    new = _setup(db, users, clock)
    t = new()
    agent = users['atendente']
    svc.add_message(db, agent, t, body='Olá', internal=False, now=clock.now)
    mailer = FakeMailer()
    clock.advance(hours=8, minutes=30)                                 # resolution at risk: 1.5h left
    assert send_alerts(db, mailer, clock.now) == 1
    first_deadline = t.resolution_due_at
    svc.apply_action(db, agent, t, action=Action.PEDIR_INFO, message='Detalhes?', now=clock.now)
    clock.advance(hours=5)
    assert send_alerts(db, mailer, clock.now) == 0                     # paused: quiet
    svc.add_message(db, users['cliente'], t, body='Aqui estão.', internal=False, now=clock.now)
    assert t.resolution_due_at - first_deadline == timedelta(hours=5)  # deadline moved by the pause
    assert t.resolution_due_at - clock.now == timedelta(hours=1, minutes=30)   # still 1.5h left: still at risk
    assert send_alerts(db, mailer, clock.now) == 1                     # new deadline → new alert
    assert send_alerts(db, mailer, clock.now) == 0                     # ...only once
    assert [m.subject.endswith('resolução em risco') for m in mailer.sent] == [True, True]


def test_inactive_owner_falls_back_to_managers(db, users, clock):
    new = _setup(db, users, clock)
    t = new()
    svc.assign(db, users['gestor'], t, assignee_id=users['atendente'].id, now=clock.now)
    users['atendente'].is_active = False
    db.commit()
    clock.advance(hours=5)
    mailer = FakeMailer()
    send_alerts(db, mailer, clock.now)
    assert {m.to for m in mailer.sent} == {users['gestor'].email}
