"""Local username/password login and user administration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.core.deps import AdminUser, AuthUser, DbSession
from app.core.security import create_token, hash_password, verify_password
from app.db.models import AuditLog, User
from app.schemas.api import LoginIn, TokenOut, UserIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, session: DbSession) -> TokenOut:
    state = request.app.state.ctx
    user = session.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid username or password")
    token = create_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        secret=state.config.secret_key,
        minutes=state.config.token_minutes,
    )
    return TokenOut(access_token=token, expires_in=state.config.token_minutes * 60, role=user.role)


@router.get("/me", response_model=UserOut)
def me(user: AuthUser) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role)


@router.get("/users", response_model=list[UserOut])
def list_users(session: DbSession, _: AdminUser) -> list[UserOut]:
    rows = session.scalars(select(User).order_by(User.username)).all()
    return [UserOut(id=row.id, username=row.username, role=row.role) for row in rows]


@router.post("/users", response_model=UserOut)
def create_user(body: UserIn, session: DbSession, actor: AdminUser) -> UserOut:
    if session.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=409, detail="username already exists")
    row = User(
        id=str(uuid.uuid4()),
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(row)
    session.add(AuditLog(user_id=actor.id, action="user.create", target=row.username))
    session.flush()
    return UserOut(id=row.id, username=row.username, role=row.role)


@router.delete("/users/{user_id}")
def delete_user(user_id: str, session: DbSession, actor: AdminUser) -> dict:
    if user_id == actor.id:
        raise HTTPException(status_code=400, detail="cannot delete the current user")
    row = session.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    if row.role == "admin":
        admins = session.scalar(select(func.count()).select_from(User).where(User.role == "admin"))
        if (admins or 0) <= 1:
            raise HTTPException(status_code=400, detail="cannot delete the last admin")
    session.delete(row)
    session.add(AuditLog(user_id=actor.id, action="user.delete", target=row.username))
    return {"deleted": user_id}
