from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Role, User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import get_password_hash

router = APIRouter(prefix='/users', tags=['users'])


@router.get('', response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    return db.query(User).order_by(User.role.asc(), User.full_name.asc()).all()


@router.post('', response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already exists')

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        receive_alert=payload.receive_alert,
        updated_by=admin.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch('/{user_id}', response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    data = payload.model_dump(exclude_unset=True)

    if 'email' in data:
        conflict = db.query(User).filter(User.email == data['email'], User.id != user_id).first()
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already exists')

    if 'password' in data:
        user.password_hash = get_password_hash(data.pop('password'))

    for key, value in data.items():
        setattr(user, key, value)
    user.updated_by = admin.id

    db.commit()
    db.refresh(user)
    return user


@router.get('/assignees', response_model=list[UserOut])
def list_assignees(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.EMAIL_TEAM, Role.ASSIGNEE))):
    return (
        db.query(User)
        .filter(User.role == Role.ASSIGNEE, User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )
