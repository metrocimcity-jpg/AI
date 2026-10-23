"""FastAPI app factory. Inference stays on camera threads, not this event loop."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import api, ws_router
from app.core.config import AppConfig, load_config
from app.core.logging import get_logger, setup_logging
from app.core.security import fernet_from_secret
from app.db.session import init_database, make_engine, sqlite_url
from app.ml.registry import ModelRegistry
from app.services.broadcaster import Broadcaster
from app.services.camera_manager import CameraManager
from app.services.event_service import EventService
from app.services.retention import RetentionJob

logger = get_logger("siteguard")


class AppState:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging(cfg.log_level)
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        for folder in ("snapshots", "clips", "faces"):
            (cfg.data_dir / folder).mkdir(parents=True, exist_ok=True)
        engine = make_engine(sqlite_url(cfg.data_dir))
        sessions = init_database(engine, cfg)
        registry = ModelRegistry(cfg.root)
        broadcaster = Broadcaster()
        broadcaster.loop = asyncio.get_running_loop()
        events_cfg = cfg.section("events")
        events = EventService(
            sessions,
            cfg.data_dir,
            broadcaster,
            cooldowns=dict(events_cfg.get("cooldown_seconds") or {}),
            save_clips=bool(events_cfg.get("save_clips", False)),
        )

        def decode_gallery(blob: bytes) -> np.ndarray:
            raw = fernet_from_secret(cfg.secret_key).decrypt(blob)
            vec = np.frombuffer(raw, dtype=np.float32).copy()
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec /= norm
            return vec

        cameras = CameraManager(cfg, registry, sessions, events, broadcaster, decode_gallery)
        app.state.ctx = AppState(
            config=cfg,
            engine=engine,
            sessions=sessions,
            registry=registry,
            events=events,
            cameras=cameras,
            broadcaster=broadcaster,
            started=time.time(),
        )
        cameras.start_enabled()
        retention = RetentionJob(sessions, cfg.data_dir, cfg.retention_days)
        retention.start()
        logger.info("SiteGuard Vision %s listening, face=%s", __version__, cfg.face_recognition_enabled)
        try:
            yield
        finally:
            retention.stop()
            cameras.stop_all()
            engine.dispose()

    app = FastAPI(title="SiteGuard Vision", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api)
    app.include_router(ws_router)
    _mount_files(app, cfg)
    return app


def _mount_files(app: FastAPI, cfg: AppConfig) -> None:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(cfg.data_dir)), name="media")
    samples = cfg.root / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    app.mount("/sample", StaticFiles(directory=str(samples)), name="sample")
    dist = cfg.root / "frontend" / "dist"

    @app.get("/", include_in_schema=False, response_model=None)
    def index() -> FileResponse | JSONResponse:
        page = dist / "index.html"
        if page.is_file():
            return FileResponse(page)
        return JSONResponse(
            {"name": "SiteGuard Vision", "health": "/api/health", "version": __version__}
        )

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith(("api", "media", "sample", "ws", "docs")):
            raise HTTPException(status_code=404)
        if dist.is_dir():
            candidate = (dist / full_path).resolve()
            root = dist.resolve()
            if candidate.is_file() and (candidate == root or root in candidate.parents):
                return FileResponse(candidate)
            page = dist / "index.html"
            if page.is_file():
                return FileResponse(page)
        raise HTTPException(status_code=404, detail="frontend is not built")


app = create_app()


if __name__ == "__main__":
    import uvicorn

    conf = load_config()
    uvicorn.run(
        "app.main:app",
        host=conf.host,
        port=conf.port,
        factory=False,
    )
