"""SQLite schema for SiteGuard. Paths stored in the database are relative."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(32))
    polygon_json: Mapped[list] = mapped_column(JSON, default=list)
    schedule_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    employee_id: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(64), default="")
    authorized_zones_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="worker", cascade="all, delete-orphan"
    )


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    embedding_blob: Mapped[bytes] = mapped_column(LargeBinary)
    model: Mapped[str] = mapped_column(String(64), default="sface")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    worker: Mapped[Worker] = relationship(back_populates="embeddings")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_camera_ts", "camera_id", "ts"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="open")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    zone_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    clip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ack_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PostureSample(Base):
    __tablename__ = "posture_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(36), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    track_id: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32))


class PPESample(Base):
    __tablename__ = "ppe_samples"
    __table_args__ = (Index("ix_ppe_samples_ts", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(36), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    track_id: Mapped[int] = mapped_column(Integer)
    helmet: Mapped[str] = mapped_column(String(16), default="unknown")
    vest: Mapped[str] = mapped_column(String(16), default="unknown")
    gloves: Mapped[str] = mapped_column(String(16), default="unknown")
    boots: Mapped[str] = mapped_column(String(16), default="unknown")
    goggles: Mapped[str] = mapped_column(String(16), default="unknown")
    harness: Mapped[str] = mapped_column(String(16), default="unknown")


class MaterialCount(Base):
    __tablename__ = "material_counts"
    __table_args__ = (
        Index("ix_material_counts_bucket_class", "ts_bucket", "class_name"),
        UniqueConstraint("camera_id", "ts_bucket", "class_name", name="uq_material_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(36), index=True)
    ts_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    class_name: Mapped[str] = mapped_column(String(64))
    count: Mapped[int] = mapped_column(Integer, default=0)
    area_ratio: Mapped[float] = mapped_column(Float, default=0.0)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("worker_id", "camera_id", "date", name="uq_attendance_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(36), index=True)
    camera_id: Mapped[str] = mapped_column(String(36))
    date: Mapped[str] = mapped_column(String(10))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
