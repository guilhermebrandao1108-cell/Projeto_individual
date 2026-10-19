"""Queue paging and SLA filters, which run in SQL."""
from datetime import timedelta

import pytest

from app.domain.sla import SlaState
from app.domain.workflow import Action
from app.models import Category
from app.services import tickets as svc


def _ids(page):
    return [t['id'] for t in page['items']]


def test_pagination_is_stable_and_counts_the_total(client, auth, open_ticket, clock):
    created = []
    for _ in range(7):
        created.append(open_ticket()['id'])
        clock.advance(minutes=1)
    first = client.get('/tickets?limit=3', headers=auth['atendente']).json()
    second = client.get('/tickets?limit=3&offset=3', headers=auth['atendente']).json()
    last = client.get('/tickets?limit=3&offset=6', headers=auth['atendente']).json()
    assert first['total'] == second['total'] == 7
    assert _ids(first) + _ids(second) + _ids(last) == created   # same queue order, no gaps or repeats
    assert (first['limit'], second['offset']) == (3, 3)


@pytest.mark.parametrize('query', ['limit=0', 'limit=201', 'offset=-1'])
def test_paging_limits_are_validated(client, auth, query):
    assert client.get(f'/tickets?{query}', headers=auth['atendente']).status_code == 422


def test_open_only_and_shortcut_counts(client, auth, open_ticket, clock):
    a, b = open_ticket(), open_ticket()
    client.post(f"/tickets/{a['id']}/resolve", json={'message': 'Resolvido.'}, headers=auth['atendente'])
    client.post(f"/tickets/{a['id']}/confirm", json={}, headers=auth['cliente'])
    clock.advance(hours=5)                                       # b: first response overdue
    page = client.get('/tickets?open_only=true', headers=auth['atendente']).json()
    assert _ids(page) == [b['id']] and page['total'] == 1
    assert page['open_overdue'] == 1 and page['open_at_risk'] == 0
    everything = client.get('/tickets', headers=auth['atendente']).json()
    assert everything['total'] == 2 and everything['open_overdue'] == 1   # counts ignore the status filter


def test_sql_filters_match_the_python_rule(db, users, clock):
    """Every ticket, at several instants, is in the SQL result for a state iff the Python rule says so."""
    queue = Category(name='Teste', first_response_hours=4, resolution_hours=10)
    db.add(queue)
    db.commit()
    customer, agent = users['cliente'], users['atendente']
    make = lambda: svc.create_ticket(db, customer, title='Chamado de teste', description='Descrição do chamado.',
                                     category_id=queue.id, priority='media', now=clock.now)
    tickets = [make() for _ in range(6)]
    t_answered, t_paused, t_late_pause, t_resolved, t_reopened, _untouched = tickets
    clock.advance(hours=1)
    svc.add_message(db, agent, t_answered, body='Olá', internal=False, now=clock.now)
    svc.apply_action(db, agent, t_paused, action=Action.INICIAR, message=None, now=clock.now)
    svc.apply_action(db, agent, t_paused, action=Action.PEDIR_INFO, message='Número do pedido?', now=clock.now)
    svc.propose_resolution(db, agent, t_resolved, message='Feito.', now=clock.now)
    svc.propose_resolution(db, agent, t_reopened, message='Feito.', now=clock.now)
    clock.advance(hours=11)                                      # past every resolution deadline
    svc.apply_action(db, agent, t_late_pause, action=Action.INICIAR, message=None, now=clock.now)
    svc.apply_action(db, agent, t_late_pause, action=Action.PEDIR_INFO, message='Detalhes?', now=clock.now)
    svc.reject_resolution(db, customer, t_reopened, message='Não resolveu.', now=clock.now)

    seen = set()
    for hours in (-11.5, -10, -9, -8.2, -1, 0, 5):              # instants before, around and after the deadlines
        now = clock.now + timedelta(hours=hours)
        for state in SlaState:
            expected = {t.id for t in tickets if state in (svc.sla_view(t, now).first_response, svc.sla_view(t, now).resolution)}
            got = {t.id for t in svc.list_tickets(db, agent, now, sla_state=state, limit=200).items}
            assert got == expected, (hours, state)
            if expected:
                seen.add(state)
    assert seen == set(SlaState)                                 # the scenario exercises every state
