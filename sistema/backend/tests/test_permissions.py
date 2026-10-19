"""Who can do what. Customers must never see or act on other people's tickets."""
import pytest


def test_requires_authentication(client):
    assert client.get('/tickets').status_code == 401
    assert client.get('/tickets', headers={'Authorization': 'Bearer invalido'}).status_code == 401


def test_register_and_login(client):
    r = client.post('/auth/register', json={'name': 'Fábio', 'email': 'Fabio@Ex.com', 'password': 'uma-senha-boa'})
    assert r.status_code == 201 and r.json()['role'] == 'cliente'
    assert client.post('/auth/register', json={'name': 'Fábio', 'email': 'fabio@ex.com', 'password': 'uma-senha-boa'}).status_code == 409
    assert client.post('/auth/token', data={'username': 'fabio@ex.com', 'password': 'errada'}).status_code == 401
    token = client.post('/auth/token', data={'username': 'fabio@ex.com', 'password': 'uma-senha-boa'}).json()['access_token']
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()['email'] == 'fabio@ex.com'


def test_register_cannot_choose_role(client):
    r = client.post('/auth/register', json={'name': 'Hacker', 'email': 'h@ex.com', 'password': 'uma-senha-boa', 'role': 'gestor'})
    assert r.json()['role'] == 'cliente'


def test_inactive_user_is_rejected(client, auth, users, db):
    users['atendente'].is_active = False
    db.commit()
    assert client.get('/tickets', headers=auth['atendente']).status_code == 401


def test_customer_sees_only_own_tickets(client, auth, open_ticket):
    mine = open_ticket()
    theirs = open_ticket(headers=auth['outro_cliente'])
    assert [t['id'] for t in client.get('/tickets', headers=auth['cliente']).json()] == [mine['id']]
    assert client.get(f"/tickets/{theirs['id']}", headers=auth['cliente']).status_code == 404  # not 403: no id leak
    assert client.post(f"/tickets/{theirs['id']}/messages", json={'body': 'oi'}, headers=auth['cliente']).status_code == 404


def test_only_customers_open_tickets(client, auth, open_ticket):
    r = client.post('/tickets', json={'title': 'Teste interno', 'description': 'Chamado aberto pela equipe.', 'category_id': 1},
                    headers=auth['atendente'])
    assert r.status_code == 403


def test_customer_cannot_write_internal_notes(client, auth, open_ticket):
    t = open_ticket()
    r = client.post(f"/tickets/{t['id']}/messages", json={'body': 'nota', 'internal': True}, headers=auth['cliente'])
    assert r.status_code == 403


@pytest.mark.parametrize('path,payload', [
    ('resolve', {'message': 'Resolvi sozinho.'}),
    ('actions', {'action': 'iniciar'}),
    ('assign', {'assignee_id': 1}),
])
def test_customer_cannot_use_staff_endpoints(client, auth, open_ticket, path, payload):
    t = open_ticket()
    assert client.post(f"/tickets/{t['id']}/{path}", json=payload, headers=auth['cliente']).status_code == 403


def test_staff_cannot_confirm_for_customer(client, auth, open_ticket):
    t = open_ticket()
    client.post(f"/tickets/{t['id']}/resolve", json={'message': 'Resolvido.'}, headers=auth['atendente'])
    assert client.post(f"/tickets/{t['id']}/confirm", json={}, headers=auth['gestor']).status_code == 403


def test_agent_can_take_unassigned_but_only_manager_transfers(client, auth, open_ticket, users):
    t = open_ticket()
    me, other = users['atendente'], users['atendente2']
    assert client.post(f"/tickets/{t['id']}/assign", json={'assignee_id': other.id}, headers=auth['atendente']).status_code == 403
    assert client.post(f"/tickets/{t['id']}/assign", json={'assignee_id': me.id}, headers=auth['atendente']).status_code == 200
    assert client.post(f"/tickets/{t['id']}/assign", json={'assignee_id': other.id}, headers=auth['atendente2']).status_code == 403
    t = client.post(f"/tickets/{t['id']}/assign", json={'assignee_id': other.id}, headers=auth['gestor']).json()
    assert t['assignee']['id'] == other.id and t['transfer_count'] == 1


def test_cannot_assign_to_customer(client, auth, open_ticket, users):
    t = open_ticket()
    r = client.post(f"/tickets/{t['id']}/assign", json={'assignee_id': users['cliente'].id}, headers=auth['gestor'])
    assert r.status_code == 404


def test_manager_only_endpoints(client, auth):
    new_category = {'name': 'Entrega', 'first_response_hours': 8, 'resolution_hours': 72}
    assert client.post('/categories', json=new_category, headers=auth['atendente']).status_code == 403
    assert client.post('/categories', json=new_category, headers=auth['gestor']).status_code == 201
    assert client.get('/metrics/overview', headers=auth['atendente']).status_code == 403
    staff = {'name': 'Novo Atendente', 'email': 'novo@ex.com', 'password': 'senha-segura', 'role': 'atendente'}
    assert client.post('/users', json=staff, headers=auth['atendente']).status_code == 403
    assert client.post('/users', json=staff, headers=auth['gestor']).status_code == 201


def test_category_sla_validation(client, auth):
    bad = {'name': 'Inválida', 'first_response_hours': 10, 'resolution_hours': 5}
    assert client.post('/categories', json=bad, headers=auth['gestor']).status_code == 422
