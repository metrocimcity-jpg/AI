# 07 — Offline / Air-gapped Deployment

## 1. Build bundle on a connected machine
```bash
# Python wheels
pip download -r backend/requirements.txt -d bundle/wheels
# Frontend
cd frontend && npm ci && npm run build && cd ..        # outputs frontend/dist
# Models (download + export once)
python scripts/export_models.py --out models/
# Docker (optional)
docker build -f docker/Dockerfile.backend -t siteguard:latest .
docker save siteguard:latest | gzip > bundle/siteguard-image.tgz
# Package
tar czf siteguard-offline.tgz . --exclude=node_modules --exclude=data
```
Include: Python wheels, `frontend/dist`, `models/` + `manifest.json` (with sha256), fonts (already bundled), default configs, install scripts.

## 2. Install on target (no internet)
```bash
tar xzf siteguard-offline.tgz && cd construction-vision
python -m venv .venv && source .venv/bin/activate
pip install --no-index --find-links bundle/wheels -r backend/requirements.txt
cp .env.example .env            # set SECRET_KEY, FACE_KEY, ADMIN_PASSWORD
python scripts/seed_demo.py     # optional demo video + sample data
./run.sh                        # uvicorn serves API + dashboard on :8000
```
Docker alternative: `docker load < bundle/siteguard-image.tgz && docker compose up -d`.

## 3. Hardware guidance
| Setup | Spec | Capacity |
|---|---|---|
| Entry | 8-core CPU, 16 GB RAM, SSD | 1–2 cams, small models, OpenVINO |
| Standard | RTX 3060/4060, 32 GB RAM | 4–6 cams @ 10–15 FPS |
| Edge | Jetson Orin NX 16 GB | 2–4 cams, TensorRT |
Storage: ~1–2 GB/day/camera with snapshots + 10 s event clips; retention job purges per policy.

## 4. Network & security
- Bind to LAN interface only; optional self-signed HTTPS (`scripts/gen_cert.sh`).
- Cameras on isolated VLAN; RTSP credentials stored in `.env`/encrypted DB field.
- Firewall: only port 8000 (or 443) inbound from site LAN.
- Backups: nightly `data/` snapshot + `scripts/backup.sh`; restore via Settings page.
- Updates: signed offline update package (`siteguard-update-x.y.z.tgz`) applied by script; models verified via sha256.

## 5. Offline verification checklist
- [ ] Unplug network → app boots, dashboard loads, fonts/icons render
- [ ] `grep -R "http" frontend/dist | grep -v localhost` shows no external asset URLs
- [ ] No outbound connection attempts (`ss -tp` / firewall log) during a 10-min run
- [ ] Missing model file → clear error banner, app does not crash or try to download
- [ ] Ultralytics/HF/OpenCV env vars set: `YOLO_OFFLINE=1`, `HF_HUB_OFFLINE=1`, `ULTRALYTICS_SETTINGS_SYNC=False`
