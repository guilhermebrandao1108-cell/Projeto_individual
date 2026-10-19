"""The indicators the case study proposes for the pilot."""
import pytest


def _resolve(client, auth, ticket_id, message='Solução aplicada.'):
    return client.post(f'/tickets/{ticket_id}/resolve', json={'message': message}, headers=auth['atendente'])


def test_overview(client, auth, open_ticket, clock):
    # 1) answered on time, confirmed with rating 4
    a = open_ticket()
    clock.advance(hours=1)
    _resolve(client, auth, a['id'])
    client.post(f"/tickets/{a['id']}/confirm", json={'satisfaction': 4}, headers=auth['cliente'])
    # 2) answered late (5h > 4h), rejected once then confirmed without rating
    b = open_ticket()
    clock.advance(hours=5)
    _resolve(client, auth, b['id'])
    client.post(f"/tickets/{b['id']}/reject", json={'message': 'Ainda com problema.'}, headers=auth['cliente'])
    _resolve(client, auth, b['id'], 'Agora sim, corrigido.')
    client.post(f"/tickets/{b['id']}/confirm", json={}, headers=auth['cliente'])
    # 3) never answered and overdue
    open_ticket()
    clock.advance(hours=5)

    m = client.get('/metrics/overview', headers=auth['gestor']).json()
    assert m['tickets'] == 3 and m['open_tickets'] == 1 and m['open_overdue'] == 1
    assert m['first_response_within_sla'] == pytest.approx(1 / 3)  # overdue pending counts as a failure
    assert m['confirmed_resolution_rate'] == 1.0
    assert m['reopen_rate'] == pytest.approx(1 / 2)
    assert m['satisfaction_coverage'] == pytest.approx(1 / 2)
    assert m['satisfaction_avg'] == 4
    assert m['first_response_p90_hours'] == pytest.approx(4.6)       # quantile of [1h, 5h]
    assert m['by_category'][0]['category'] == 'Cobrança'


def test_empty_overview_has_no_division_by_zero(client, auth):
    m = client.get('/metrics/overview', headers=auth['gestor']).json()
    assert m['tickets'] == 0 and m['first_response_within_sla'] is None and m['by_category'] == []
