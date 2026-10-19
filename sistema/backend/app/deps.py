"""FastAPI dependencies: database session, current user, role checks and the clock."""
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User
from .security import decode_access_token
from .timeutils import utcnow

oauth2 = OAuth2PasswordBearer(tokenUrl='/auth/token')
DB = Annotated[Session, Depends(get_db)]


def get_now() -> datetime:
    """Overridden in tests to control time (SLA rules depend on it)."""
    return utcnow()


Now = Annotated[datetime, Depends(get_now)]


def get_current_user(db: DB, token: Annotated[str, Depends(oauth2)]) -> User:
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Credenciais inválidas', headers={'WWW-Authenticate': 'Bearer'})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, 'Perfil sem permissão para esta operação')
        return user
    return check


Staff = Annotated[User, Depends(require_roles(Role.ATENDENTE, Role.GESTOR))]
Manager = Annotated[User, Depends(require_roles(Role.GESTOR))]
