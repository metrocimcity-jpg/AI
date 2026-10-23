"""Engine, sessions, and first-boot admin seed."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import Base, User

logger = get_logger("siteguard.db")


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, future=True)

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record) -> None:  # type: ignore[no-untyped-def]
        if not database_url.startswith("sqlite"):
            return
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def sqlite_url(data_dir: Path) -> str:
    data_dir.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + (data_dir / "db.sqlite").as_posix()


def init_database(engine: Engine, config: AppConfig) -> sessionmaker[Session]:
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with factory() as session:
        existing = session.scalar(select(User).where(User.username == config.admin_username))
        if existing is None:
            session.add(
                User(
                    id=str(uuid.uuid4()),
                    username=config.admin_username,
                    password_hash=hash_password(config.admin_password),
                    role="admin",
                )
            )
            session.commit()
            logger.info("seeded admin user %s", config.admin_username)
        if config.admin_password == "changeme" or config.secret_key == "dev-change-me":
            logger.warning("default admin password or SECRET_KEY is still in use; change .env")
    return factory


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
