"""Brute-force protection for login: too many failures for the same account and client → HTTP 429.

In-memory and per process, which is enough for a single instance. With several instances
behind a load balancer this state would live in a shared store such as Redis.
"""
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock


class TooManyAttempts(Exception):
    def __init__(self, retry_after: timedelta):
        super().__init__('Muitas tentativas de login. Tente novamente mais tarde.')
        self.retry_after_seconds = max(1, int(retry_after.total_seconds()))


class LoginThrottle:
    def __init__(self, max_failures: int = 5, window: timedelta = timedelta(minutes=15)):
        self.max_failures = max_failures
        self.window = window
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def _recent(self, key: str, now: datetime) -> deque[datetime]:
        failures = self._failures[key]
        while failures and now - failures[0] >= self.window:
            failures.popleft()
        return failures

    def check(self, key: str, now: datetime) -> None:
        with self._lock:
            failures = self._recent(key, now)
            if len(failures) >= self.max_failures:
                raise TooManyAttempts(failures[0] + self.window - now)

    def failure(self, key: str, now: datetime) -> None:
        with self._lock:
            self._recent(key, now).append(now)

    def success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_throttle = LoginThrottle()
