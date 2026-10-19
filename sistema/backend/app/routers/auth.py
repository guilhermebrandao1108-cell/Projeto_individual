from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import DB, CurrentUser, Now
from ..models import Role, User
from ..ratelimit import login_throttle
from ..schemas import RegisterIn, Token, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix='/auth', tags=['auth'])
# Verified when the e-mail does not exist, so both failures take the same time (no account enumeration by timing).
_DUMMY_HASH = hash_password('not-a-real-password')


@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: DB):
    """Self-service sign-up creates customers only; staff accounts are created by a manager."""
    user = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password), role=Role.CLIENTE)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, 'E-mail já cadastrado')
    return user


@router.post('/token', response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB, request: Request, now: Now):
    email = form.username.lower()
    key = f"{email}|{request.client.host if request.client else '-'}"
    login_throttle.check(key, now)  # 429 before even looking at the password
    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(form.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not user.is_active or not valid:
        login_throttle.failure(key, now)
        # Same message for unknown e-mail and wrong password: does not reveal which accounts exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'E-mail ou senha incorretos', headers={'WWW-Authenticate': 'Bearer'})
    login_throttle.success(key)
    return Token(access_token=create_access_token(user.id))


@router.get('/me', response_model=UserOut)
def me(user: CurrentUser):
    return user
