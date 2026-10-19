"""End-to-end ticket flows through the HTTP API."""


def test_full_lifecycle_with_customer_confirmation(client, auth, open_ticket, clock):
    t = open_ticket()
    assert t['status'] == 'aberto' and t['sla']['first_response'] == 'no_prazo'

    clock.advance(hours=1)
    r = client.post(f"/tickets/{t['id']}/messages", json={'body': 'Olá! Vou verificar a cobrança.'}, headers=auth['atendente'])
    t = r.json()
    assert t['status'] == 'em_atendimento'          # first public reply starts the work
    assert t['sla']['first_response'] == 'cumprido'

    clock.advance(hours=2)
    t = client.post(f"/tickets/{t['id']}/resolve", json={'message': 'Estorno feito, aparece em 2 dias.'}, headers=auth['atendente']).json()
    assert t['status'] == 'resolvido' and t['sla']['resolution'] == 'cumprido'
    assert t['closed_at'] is None                    # replied/proposed is not resolved

    customer_view = client.get(f"/tickets/{t['id']}", headers=auth['cliente']).json()
    assert customer_view['allowed_actions'] == ['confirmar', 'rejeitar']

    t = client.post(f"/tickets/{t['id']}/confirm", json={'satisfaction': 5, 'comment': 'Rápido!'}, headers=auth['cliente']).json()
    assert t['status'] == 'fechado' and t['satisfaction'] == 5 and t['closed_at']
    assert [e['type'] for e in t['events']] == ['criado', 'mensagem', 'status', 'status', 'mensagem', 'status', 'avaliado']


def test_rejection_reopens_and_resolution_clock_keeps_running(client, auth, open_ticket, clock):
    t = open_ticket()
    client.post(f"/tickets/{t['id']}/resolve", json={'message': 'Tente reiniciar o app.'}, headers=auth['atendente'])
    clock.advance(hours=50)
    t = client.post(f"/tickets/{t['id']}/reject", json={'message': 'Não resolveu, continuo cobrado.'}, headers=auth['cliente']).json()
    assert t['status'] == 'em_atendimento'
    assert t['reopen_count'] == 1 and t['resolved_at'] is None
    assert t['sla']['resolution'] == 'vencido'      # the earlier proposal no longer counts


def test_request_info_and_customer_reply(client, auth, open_ticket):
    t = open_ticket()
    client.post(f"/tickets/{t['id']}/actions", json={'action': 'iniciar'}, headers=auth['atendente'])
    t = client.post(f"/tickets/{t['id']}/actions", json={'action': 'pedir_info', 'message': 'Qual o final do cartão?'},
                    headers=auth['atendente']).json()
    assert t['status'] == 'aguardando_cliente' and t['first_response_at']
    t = client.post(f"/tickets/{t['id']}/messages", json={'body': 'Final 1234.'}, headers=auth['cliente']).json()
    assert t['status'] == 'em_atendimento'


def test_starting_assigns_the_agent(client, auth, open_ticket, users):
    t = open_ticket()
    t = client.post(f"/tickets/{t['id']}/actions", json={'action': 'iniciar'}, headers=auth['atendente']).json()
    assert t['assignee']['id'] == users['atendente'].id
    assert t['first_response_at'] is None           # starting is not answering the customer


def test_internal_notes_are_hidden_from_customer(client, auth, open_ticket):
    t = open_ticket()
    client.post(f"/tickets/{t['id']}/messages", json={'body': 'Cliente recorrente, priorizar.', 'internal': True}, headers=auth['atendente'])
    staff = client.get(f"/tickets/{t['id']}", headers=auth['atendente']).json()
    customer = client.get(f"/tickets/{t['id']}", headers=auth['cliente']).json()
    assert len(staff['messages']) == 1 and customer['messages'] == []
    assert staff['first_response_at'] is None       # an internal note is not a reply
    assert all(e['to_value'] != 'interna' for e in customer['events'])


def test_sla_at_risk_and_overdue_filters(client, auth, open_ticket, clock):
    t = open_ticket()
    clock.advance(hours=3, minutes=30)              # 87% of the 4h first-response window
    page = client.get('/tickets?sla=em_risco', headers=auth['atendente']).json()
    assert [x['id'] for x in page['items']] == [t['id']] and page['open_at_risk'] == 1
    clock.advance(hours=1)
    assert client.get('/tickets?sla=em_risco', headers=auth['atendente']).json()['items'] == []
    page = client.get('/tickets?sla=vencido', headers=auth['atendente']).json()
    assert [x['id'] for x in page['items']] == [t['id']] and page['open_overdue'] == 1


def test_queue_is_ordered_by_deadline(client, auth, open_ticket, db, clock):
    from app.models import Category
    urgent_queue = Category(name='Acesso à conta', first_response_hours=1, resolution_hours=8)
    db.add(urgent_queue)
    db.commit()
    slow = open_ticket()
    clock.advance(minutes=10)
    fast = open_ticket(category_id=urgent_queue.id, title='Não consigo entrar')
    ids = [t['id'] for t in client.get('/tickets', headers=auth['atendente']).json()['items']]
    assert ids == [fast['id'], slow['id']]


def test_search(client, auth, open_ticket):
    open_ticket()
    open_ticket(title='Produto chegou quebrado', description='A tela veio trincada na entrega.')
    found = client.get('/tickets?q=trincada', headers=auth['atendente']).json()['items']
    assert [t['title'] for t in found] == ['Produto chegou quebrado']


def test_closed_ticket_accepts_no_more_messages(client, auth, open_ticket):
    t = open_ticket()
    client.post(f"/tickets/{t['id']}/resolve", json={'message': 'Resolvido por aqui.'}, headers=auth['atendente'])
    client.post(f"/tickets/{t['id']}/confirm", json={}, headers=auth['cliente'])
    r = client.post(f"/tickets/{t['id']}/messages", json={'body': 'Mais uma coisa'}, headers=auth['cliente'])
    assert r.status_code == 409


def test_invalid_transition_returns_409(client, auth, open_ticket):
    t = open_ticket()
    r = client.post(f"/tickets/{t['id']}/actions", json={'action': 'pedir_info', 'message': 'Detalhes?'}, headers=auth['atendente'])
    assert r.status_code == 409


def test_sla_change_does_not_move_existing_deadlines(client, auth, open_ticket, category):
    t = open_ticket()
    client.patch(f'/categories/{category.id}', json={'first_response_hours': 1}, headers=auth['gestor'])
    after = client.get(f"/tickets/{t['id']}", headers=auth['gestor']).json()
    assert after['sla']['first_response_due_at'] == t['sla']['first_response_due_at']
    assert open_ticket()['sla']['first_response_due_at'] != t['sla']['first_response_due_at']


def _ask_info(client, auth, ticket_id):
    client.post(f'/tickets/{ticket_id}/actions', json={'action': 'iniciar'}, headers=auth['atendente'])
    return client.post(f'/tickets/{ticket_id}/actions', json={'action': 'pedir_info', 'message': 'Qual o número do pedido?'},
                       headers=auth['atendente']).json()


def test_resolution_sla_pauses_while_waiting_for_customer(client, auth, open_ticket, clock):
    t = open_ticket()                                  # resolution due in 48h
    clock.advance(hours=1)
    _ask_info(client, auth, t['id'])
    clock.advance(hours=60)                            # customer takes 60h: past the original deadline
    waiting = client.get(f"/tickets/{t['id']}", headers=auth['atendente']).json()
    assert waiting['sla']['resolution'] == 'pausado'
    assert client.get('/tickets?sla=vencido', headers=auth['atendente']).json()['items'] == []

    t = client.post(f"/tickets/{t['id']}/messages", json={'body': 'Pedido 98765.'}, headers=auth['cliente']).json()
    assert t['status'] == 'em_atendimento'
    assert t['sla']['resolution'] == 'no_prazo'
    assert t['sla_paused_seconds'] == 60 * 3600
    assert t['sla']['resolution_due_at'] > waiting['sla']['resolution_due_at']   # moved forward by the pause


def test_pausing_an_overdue_ticket_keeps_it_overdue(client, auth, open_ticket, clock):
    t = open_ticket()
    clock.advance(hours=50)                            # resolution already breached
    t = _ask_info(client, auth, t['id'])
    assert t['sla']['resolution'] == 'vencido'
