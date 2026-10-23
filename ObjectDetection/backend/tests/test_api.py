"""Health, auth, and a file camera that streams without a model on disk."""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import load_config
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "providers" in body
    assert any(item["name"] == "person_yolo" for item in body["models"])


def test_auth_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITEGUARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_PASSWORD", "changeme")
    cfg = load_config()
    cfg.auth_required = True
    cfg.autostart_cameras = False
    cfg.data_dir = tmp_path
    app = create_app(cfg)
    with TestClient(app) as test_client:
        assert test_client.get("/api/cameras").status_code == 401
        denied = test_client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
        assert denied.status_code == 401
        ok = test_client.post(
            "/api/auth/login", json={"username": "admin", "password": "changeme"}
        )
        assert ok.status_code == 200
        token = ok.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert test_client.get("/api/cameras", headers=headers).status_code == 200
        assert test_client.get("/api/auth/me", headers=headers).json()["role"] == "admin"


def _write_clip(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120)
    )
    if not writer.isOpened():
        pytest.skip("OpenCV cannot write a sample clip on this machine")
    for index in range(8):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[:, :] = (20, 40, index * 20)
        cv2.rectangle(frame, (40, 20), (80, 100), (0, 180, 255), -1)
        writer.write(frame)
    writer.release()


def test_file_camera_snapshot(client: TestClient, tmp_path: Path) -> None:
    clip = tmp_path / "demo.avi"
    _write_clip(clip)
    created = client.post(
        "/api/cameras",
        json={"name": "Gate", "source": str(clip), "enabled": True},
    )
    assert created.status_code == 200, created.text
    camera_id = created.json()["id"]
    started = client.post(f"/api/cameras/{camera_id}/start")
    assert started.status_code == 200
    jpeg = b""
    for _ in range(30):
        shot = client.get(f"/api/cameras/{camera_id}/snapshot.jpg")
        if shot.status_code == 200 and shot.content[:2] == b"\xff\xd8":
            jpeg = shot.content
            break
        time.sleep(0.1)
    assert jpeg, "capture thread did not publish a frame"
    client.post(f"/api/cameras/{camera_id}/stop")
