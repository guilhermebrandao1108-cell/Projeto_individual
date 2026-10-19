from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import DB, CurrentUser, Manager
from ..models import Category
from ..schemas import CategoryIn, CategoryOut, CategoryUpdate

router = APIRouter(prefix='/categories', tags=['categories'])


@router.get('', response_model=list[CategoryOut])
def list_categories(db: DB, _: CurrentUser, include_inactive: bool = False):
    stmt = select(Category).order_by(Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active)
    return db.scalars(stmt).all()


def _commit(db: DB) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, 'Já existe uma categoria com esse nome ou o SLA é inválido')


@router.post('', response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryIn, db: DB, _: Manager):
    category = Category(**data.model_dump())
    db.add(category)
    _commit(db)
    return category


@router.patch('/{category_id}', response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: DB, _: Manager):
    """SLA changes apply to new tickets; existing deadlines are kept, as agreed when they were opened."""
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Categoria não encontrada')
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    if category.resolution_hours < category.first_response_hours:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, 'resolution_hours deve ser ≥ first_response_hours')
    _commit(db)
    return category
