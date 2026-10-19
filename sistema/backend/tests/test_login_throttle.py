"""Brute-force protection on /auth/token."""
from datetime import datetime, timedelta, timezone

import pytest

from app.ratelimit import LoginThrottle, TooManyAttempts

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _login(client, password):
    return client.post('/auth/token', data={'username': 'ana@ex.com', 'password': password})


def test_blocks_after_five_failures_even_with_the_right_password(client, users, clock):
    for _ in range(5):
        assert _login(client, 'errada').status_code == 401
    r = _login(client, 'senha-segura')
    assert r.status_code == 429
    assert int(r.headers['Retry-After']) == 15 * 60


def test_block_expires_after_the_window(client, users, clock):
    for _ in range(5):
        _login(client, 'errada')
    clock.advance(minutes=15)
    assert _login(client, 'senha-segura').status_code == 200


def test_success_clears_previous_failures(client, users):
    for _ in range(4):
        _login(client, 'errada')
    assert _login(client, 'senha-segura').status_code == 200
    for _ in range(4):
        assert _login(client, 'errada').status_code == 401   # counter restarted


def test_accounts_are_throttled_independently(client, users):
    for _ in range(5):
        _login(client, 'errada')
    r = client.post('/auth/token', data={'username': 'bruno@ex.com', 'password': 'senha-segura'})
    assert r.status_code == 200


def test_unknown_email_gets_the_same_answer(client, users):
    r = client.post('/auth/token', data={'username': 'ninguem@ex.com', 'password': 'x'})
    assert r.status_code == 401 and r.json()['detail'] == _login(client, 'errada').json()['detail']


def test_sliding_window():
    throttle = LoginThrottle(max_failures=2, window=timedelta(minutes=10))
    throttle.failure('k', T0)
    throttle.failure('k', T0 + timedelta(minutes=8))
    with pytest.raises(TooManyAttempts) as blocked:
        throttle.check('k', T0 + timedelta(minutes=9))
    assert blocked.value.retry_after_seconds == 60          # until the oldest failure leaves the window
    throttle.check('k', T0 + timedelta(minutes=10))          # oldest failure expired: allowed again
