"""CSV export for the pilot analysis: content, privacy and access."""
import csv
import io

from app.services.export import COLUMNS


def _rows(response):
    return list(csv.DictReader(io.StringIO(response.text)))


def test_export_has_one_row_per_ticket_with_outcomes(client, auth, open_ticket, clock):
    t = open_ticket()
    clock.advance(hours=2)
    client.post(f"/tickets/{t['id']}/resolve", json={'message': 'Estorno realizado.'}, headers=auth['atendente'])
    client.post(f"/tickets/{t['id']}/confirm", json={'satisfaction': 4}, headers=auth['cliente'])
    open_ticket()

    r = client.get('/metrics/export.csv', headers=auth['gestor'])
    assert r.status_code == 200 and r.headers['content-type'].startswith('text/csv')
    assert 'attachment; filename="chamados_' in r.headers['content-disposition']
    rows = _rows(r)
    assert list(rows[0]) == COLUMNS and len(rows) == 2
    done, waiting = rows
    assert (done['status'], done['confirmado'], done['avaliacao']) == ('fechado', '1', '4')
    assert (done['horas_ate_primeira_resposta'], done['sla_primeira_resposta']) == ('2.00', 'cumprido')
    assert (waiting['horas_ate_primeira_resposta'], waiting['confirmado']) == ('', '0')


def test_export_contains_no_personal_data(client, auth, open_ticket, users):
    open_ticket()
    text = client.get('/metrics/export.csv', headers=auth['gestor']).text
    for secret in (users['cliente'].name, users['cliente'].email, 'Fui cobrado duas vezes'):
        assert secret not in text


def test_export_is_manager_only(client, auth):
    assert client.get('/metrics/export.csv', headers=auth['atendente']).status_code == 403
    assert client.get('/metrics/export.csv', headers=auth['cliente']).status_code == 403
