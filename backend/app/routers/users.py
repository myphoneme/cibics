from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Record, Role, User
from app.schemas import UserCreate, UserOut, UserSelfUpdate, UserUpdate
from app.security import get_password_hash, verify_password

router = APIRouter(prefix='/users', tags=['users'])


@router.get('', response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    return (
        db.query(User)
        .filter(User.is_active.is_(True), User.deleted_at.is_(None))
        .order_by(User.role.asc(), User.full_name.asc())
        .all()
    )


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


@router.patch('/me', response_model=UserOut)
def update_self(
    payload: UserSelfUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No fields provided')

    if 'current_password' in data and 'new_password' not in data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='new_password is required when current_password is provided',
        )

    if 'new_password' in data:
        current_password = data.get('current_password') or ''
        if not current_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Current password is required')
        if not verify_password(current_password, current_user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Current password is incorrect')
        current_user.password_hash = get_password_hash(data['new_password'])

    if 'full_name' in data and data['full_name'] is not None:
        cleaned_name = data['full_name'].strip()
        if len(cleaned_name) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Name must be at least 2 characters')
        current_user.full_name = cleaned_name

    current_user.updated_by = current_user.id
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch('/{user_id}', response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    user = db.get(User, user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    data = payload.model_dump(exclude_unset=True)

    if 'role' in data and data['role'] != user.role and user.role == Role.SUPER_ADMIN:
        active_super_admins = (
            db.query(User)
            .filter(
                User.role == Role.SUPER_ADMIN,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .count()
        )
        if active_super_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='At least one active super admin must remain',
            )

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


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    user = db.get(User, user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='You cannot delete your own user')

    if user.role == Role.SUPER_ADMIN:
        active_super_admins = (
            db.query(User)
            .filter(
                User.role == Role.SUPER_ADMIN,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .count()
        )
        if active_super_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='At least one active super admin must remain',
            )

    db.query(Record).filter(Record.assignee_id == user.id).update(
        {Record.assignee_id: None, Record.updated_by: admin.id},
        synchronize_session=False,
    )

    user.is_active = False
    user.receive_alert = False
    user.updated_by = admin.id
    user.deleted_by = admin.id
    user.deleted_at = datetime.now(timezone.utc)

    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/assignees', response_model=list[UserOut])
def list_assignees(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.EMAIL_TEAM, Role.ASSIGNEE)),
):
    return (
        db.query(User)
        .filter(User.role.in_([Role.ASSIGNEE, Role.SUPER_ADMIN]), User.is_active.is_(True), User.deleted_at.is_(None))
        .order_by(User.full_name.asc())
        .all()
    )
