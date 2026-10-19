from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import DB, Manager, Now, Staff
from ..models import Role, User
from ..schemas import StaffUpdate, StaffUpdateOut, UserCreate, UserOut
from ..security import hash_password
from ..services import users as svc
from ..services.tickets import STAFF_ROLES

router = APIRouter(prefix='/users', tags=['users'])


@router.get('', response_model=list[UserOut])
def list_staff(db: DB, _: Staff, include_inactive: bool = False):
    """The team (agents and managers). Customers are never listed: their e-mails stay private."""
    stmt = select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.name)
    if not include_inactive:
        stmt = stmt.where(User.is_active)
    return db.scalars(stmt).all()


@router.post('', response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: DB, _: Manager):
    if data.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, 'Clientes se cadastram sozinhos em /auth/register')
    user = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, 'E-mail já cadastrado')
    return user


@router.patch('/{user_id}', response_model=StaffUpdateOut)
def update_staff(user_id: int, data: StaffUpdate, db: DB, actor: Manager, now: Now):
    """Deactivating a member returns their open tickets to the queue."""
    user, released = svc.update_staff(db, actor, user_id, is_active=data.is_active, role=data.role, now=now)
    return StaffUpdateOut(user=UserOut.model_validate(user), released_tickets=released)
