"""Team management: deactivation, role changes and the safety rules around them."""


def _patch(client, auth, user, who='gestor', **body):
    return client.patch(f'/users/{user.id}', json=body, headers=auth[who])


def test_deactivating_an_agent_returns_open_tickets_to_the_queue(client, auth, users, open_ticket):
    agent = users['atendente']
    open_one, closed_one = open_ticket(), open_ticket()
    for t in (open_one, closed_one):
        client.post(f"/tickets/{t['id']}/assign", json={'assignee_id': agent.id}, headers=auth['atendente'])
    client.post(f"/tickets/{closed_one['id']}/resolve", json={'message': 'Resolvido.'}, headers=auth['atendente'])
    client.post(f"/tickets/{closed_one['id']}/confirm", json={}, headers=auth['cliente'])

    r = _patch(client, auth, agent, is_active=False)
    assert r.status_code == 200 and r.json()['released_tickets'] == 1
    released = client.get(f"/tickets/{open_one['id']}", headers=auth['gestor']).json()
    assert released['assignee'] is None
    assert released['events'][-1]['type'] == 'atribuido' and released['events'][-1]['from_value'] == agent.name
    closed = client.get(f"/tickets/{closed_one['id']}", headers=auth['gestor']).json()
    assert closed['assignee']['id'] == agent.id                  # history of closed tickets is kept
    assert client.get('/tickets', headers=auth['atendente']).status_code == 401   # can no longer sign in


def test_reactivate_and_promote(client, auth, users):
    agent = users['atendente2']
    _patch(client, auth, agent, is_active=False)
    r = _patch(client, auth, agent, is_active=True, role='gestor')
    assert r.json()['user']['is_active'] is True and r.json()['user']['role'] == 'gestor'


def test_manager_cannot_lock_themselves_out(client, auth, users):
    assert _patch(client, auth, users['gestor'], is_active=False).status_code == 409
    assert _patch(client, auth, users['gestor'], role='atendente').status_code == 409


def test_customers_are_not_team_members(client, auth, users):
    assert _patch(client, auth, users['cliente'], is_active=False).status_code == 404
    assert _patch(client, auth, users['atendente'], role='cliente').status_code == 409
    staff = {'name': 'Novo', 'email': 'novo@ex.com', 'password': 'senha-segura', 'role': 'cliente'}
    assert client.post('/users', json=staff, headers=auth['gestor']).status_code == 422


def test_only_managers_change_the_team(client, auth, users):
    assert _patch(client, auth, users['atendente2'], who='atendente', is_active=False).status_code == 403


def test_team_list_never_exposes_customers(client, auth, users):
    emails = {u['email'] for u in client.get('/users', headers=auth['atendente']).json()}
    assert users['cliente'].email not in emails and users['atendente'].email in emails
    _patch(client, auth, users['atendente2'], is_active=False)
    active = {u['email'] for u in client.get('/users', headers=auth['gestor']).json()}
    everyone = {u['email'] for u in client.get('/users?include_inactive=true', headers=auth['gestor']).json()}
    assert users['atendente2'].email not in active and users['atendente2'].email in everyone
