import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.entities import User, UserRole

ACCESS_COOKIE = "qpi_access"
REFRESH_COOKIE = "qpi_refresh"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, token_type: str = "access") -> str:
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    # Fractional `iat` so a revocation (User.sessions_invalidated_at) is exact to the millisecond.
    to_encode.update({"exp": now + expires_delta, "iat": now.timestamp(), "type": token_type})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    return create_access_token(
        {"sub": user_id}, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), token_type="refresh"
    )


def _credentials_error(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _credentials_error("Session expired")
    except jwt.PyJWTError:
        raise _credentials_error()
    # Tokens minted without a type (e.g. by older clients/tests) are treated as access tokens.
    if payload.get("type", "access") != expected_type:
        raise _credentials_error()
    return payload


def token_is_revoked(user: User, payload: dict) -> bool:
    """True if the token predates the user's last "sign out everywhere" / password reset."""
    cutoff = user.sessions_invalidated_at
    if cutoff is None:
        return False
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    try:
        issued = float(payload.get("iat"))
    except (TypeError, ValueError):
        return True
    return issued < cutoff.timestamp()


def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Authorization header or the httpOnly session cookie."""
    token = bearer_token or request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise _credentials_error("Not authenticated")
    payload = decode_access_token(token)
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        raise _credentials_error()
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_error()
    if token_is_revoked(user, payload):
        raise _credentials_error("Session expired")
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action")
        return user

    return _dependency


ARCHIVE_ROLES = (UserRole.ARCHIVAL_ADMIN, UserRole.SYSTEM_ADMIN)
SYLLABUS_ROLES = (UserRole.DEPT_HEAD, UserRole.ARCHIVAL_ADMIN, UserRole.SYSTEM_ADMIN)
