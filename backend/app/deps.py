from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Role, User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbDep, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credential_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=['HS256'])
        subject = payload.get('sub')
        if subject is None:
            raise credential_error
        user_id = int(subject)
    except (JWTError, ValueError):
        raise credential_error

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credential_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: Role):
    def role_checker(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not enough permissions')
        return user

    return role_checker
