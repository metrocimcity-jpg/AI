"""Load config/settings.yaml and optional .env overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


def project_root() -> Path:
    override = os.environ.get("SITEGUARD_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    root: Path
    data_dir: Path
    secret_key: str = "dev-change-me"
    admin_username: str = "admin"
    admin_password: str = "changeme"
    auth_required: bool = True
    autostart_cameras: bool = True
    face_recognition_enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    retention_days: int = 30
    token_minutes: int = 720
    raw: dict[str, Any] = Field(default_factory=dict)

    def section(self, name: str) -> dict[str, Any]:
        value = self.raw.get(name, {})
        return value if isinstance(value, dict) else {}


def load_config(root: Path | None = None) -> AppConfig:
    root = root or project_root()
    _load_dotenv(root / ".env")
    settings_path = root / "config" / "settings.yaml"
    raw: dict[str, Any] = {}
    if settings_path.is_file():
        loaded = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            raw = loaded
    runtime = raw.get("runtime") if isinstance(raw.get("runtime"), dict) else {}
    auth = raw.get("auth") if isinstance(raw.get("auth"), dict) else {}
    face = raw.get("face") if isinstance(raw.get("face"), dict) else {}

    data_env = os.environ.get("SITEGUARD_DATA_DIR")
    data_dir = Path(data_env) if data_env else root / "data"
    host = os.environ.get("SITEGUARD_HOST", str(runtime.get("host", "127.0.0.1")))
    port = int(os.environ.get("SITEGUARD_PORT", runtime.get("port", 8000)))
    face_enabled = bool(face.get("enabled", False))
    if "FACE_RECOGNITION_ENABLED" in os.environ:
        face_enabled = _as_bool(os.environ["FACE_RECOGNITION_ENABLED"])
    auth_required = True
    if "SITEGUARD_AUTH_REQUIRED" in os.environ:
        auth_required = _as_bool(os.environ["SITEGUARD_AUTH_REQUIRED"])
    autostart = True
    if "SITEGUARD_AUTOSTART" in os.environ:
        autostart = _as_bool(os.environ["SITEGUARD_AUTOSTART"])

    return AppConfig(
        root=root,
        data_dir=data_dir,
        secret_key=os.environ.get("SECRET_KEY", "dev-change-me"),
        admin_username=os.environ.get("ADMIN_USERNAME", "admin"),
        admin_password=os.environ.get("ADMIN_PASSWORD", "changeme"),
        auth_required=auth_required,
        autostart_cameras=autostart,
        face_recognition_enabled=face_enabled,
        host=host,
        port=port,
        log_level=str(runtime.get("log_level", "INFO")),
        retention_days=int(raw.get("retention_days", 30)),
        token_minutes=int(auth.get("token_minutes", 720)),
        raw=raw,
    )
