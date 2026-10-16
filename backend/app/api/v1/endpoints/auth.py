import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_current_user,
    hash_password,
    token_is_revoked,
    verify_password,
)
from app.db.session import get_db
from app.models.entities import Department, User, UserRole
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.audit_service import AuditService
from app.services.runtime_settings import get_runtime_settings

router = APIRouter()

# Pre-computed hash so failed logins for unknown emails take as long as wrong passwords.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _set_session_cookies(response: Response, user: User) -> None:
    common = {"httponly": True, "secure": settings.cookie_secure, "samesite": "lax", "path": "/"}
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token({"sub": str(user.id), "role": user.role.value}),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(str(user.id)),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **common,
    )


def _clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")


def _load_user(db: Session, user_id) -> User:
    return db.scalar(select(User).options(joinedload(User.department)).where(User.id == user_id))


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not get_runtime_settings(db).registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is currently disabled. Please contact an administrator.",
        )
    email = payload.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    department = None
    if payload.department_code:
        department = db.scalar(select(Department).where(Department.code == payload.department_code))
        if department is None:
            raise HTTPException(status_code=422, detail="Unknown department")
    # Self-registration always creates faculty accounts; elevated roles are assigned by administrators.
    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.FACULTY,
        department_id=department.id if department else None,
    )
    db.add(user)
    db.commit()
    AuditService.log_request(db, request, "USER_REGISTER", user.id, actor_id=user.id)
    _set_session_cookies(response, user)
    return _load_user(db, user.id)


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = _authenticate(db, payload.email, payload.password)
    user.last_login_at = datetime.now(timezone.utc)
    AuditService.log_request(db, request, "USER_LOGIN", user.id, actor_id=user.id)
    _set_session_cookies(response, user)
    return _load_user(db, user.id)


@router.post("/token", response_model=TokenOut, include_in_schema=True)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow for API clients and the Swagger UI (returns a bearer token)."""
    user = _authenticate(db, form.username, form.password)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return TokenOut(access_token=create_access_token({"sub": str(user.id), "role": user.role.value}))


@router.post("/refresh", response_model=UserOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token_value = request.cookies.get(REFRESH_COOKIE)
    if not token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(token_value, expected_type="refresh")
    try:
        user = _load_user(db, uuid.UUID(str(payload.get("sub"))))
    except ValueError:
        user = None
    if user is None or not user.is_active or token_is_revoked(user, payload):
        _clear_session_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    _set_session_cookies(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookies(response)
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _load_user(db, user.id)
