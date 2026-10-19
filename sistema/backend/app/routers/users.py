from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import DB, Manager, Staff
from ..models import Role, User
from ..schemas import UserCreate, UserOut
from ..security import hash_password

router = APIRouter(prefix='/users', tags=['users'])


@router.get('', response_model=list[UserOut])
def list_users(db: DB, _: Staff, role: Role | None = None):
    stmt = select(User).order_by(User.name)
    if role:
        stmt = stmt.where(User.role == role)
    return db.scalars(stmt).all()


@router.post('', response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: DB, _: Manager):
    user = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, 'E-mail já cadastrado')
    return user
