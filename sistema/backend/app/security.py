"""Password hashing (scrypt, standard library) and JWT access tokens."""
import base64
import hashlib
import hmac
import os
from datetime import timedelta

import jwt

from .config import settings
from .timeutils import utcnow

_N, _R, _P = 2**14, 8, 1
ALGORITHM = 'HS256'


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f'scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split('$')
    except ValueError:
        return False
    if scheme != 'scrypt':
        return False
    candidate = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=_N, r=_R, p=_P)
    return hmac.compare_digest(candidate, base64.b64decode(digest))


def create_access_token(user_id: int) -> str:
    now = utcnow()
    payload = {'sub': str(user_id), 'iat': now, 'exp': now + timedelta(minutes=settings.token_minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        return int(jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])['sub'])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
