"""Request dependencies: current user and application state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.core.security import decode_token
from app.db.models import User


@dataclass
class CurrentUser:
    id: str
    username: str
    role: str


def get_state(request: Request):
    return request.app.state.ctx


def get_db(request: Request):
    state = get_state(request)
    session: Session = state.sessions()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _token_from_request(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    query = request.query_params.get("token")
    return query or None


def get_current_user(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    state = get_state(request)
    config: AppConfig = state.config
    if not config.auth_required:
        return CurrentUser(id="dev", username="dev", role="admin")
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        payload = decode_token(token, config.secret_key)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    user = session.get(User, str(payload.get("sub")))
    if user is None:
        raise HTTPException(status_code=401, detail="unknown user")
    return CurrentUser(id=user.id, username=user.username, role=user.role)


def require(*roles: str):
    def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return dependency


DbSession = Annotated[Session, Depends(get_db)]
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
AdminUser = Annotated[CurrentUser, Depends(require("admin"))]
OfficerUser = Annotated[CurrentUser, Depends(require("admin", "officer"))]


def session_factory(request: Request) -> sessionmaker[Session]:
    return get_state(request).sessions
