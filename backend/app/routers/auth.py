from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import CurrentUser
from app.models import Role, User
from app.schemas import LoginRequest, Token, UserOut
from app.security import create_access_token, get_password_hash, verify_password

router = APIRouter(prefix='/auth', tags=['auth'])
settings = get_settings()


@router.post('/bootstrap', response_model=UserOut)
def bootstrap_admin(db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.role == Role.SUPER_ADMIN).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Super admin already exists')

    admin = User(
        full_name=settings.default_super_admin_name,
        email=settings.default_super_admin_email,
        password_hash=get_password_hash(settings.default_super_admin_password),
        role=Role.SUPER_ADMIN,
        is_active=True,
        receive_alert=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@router.post('/login', response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get('/me', response_model=UserOut)
def me(current_user: CurrentUser):
    return current_user
