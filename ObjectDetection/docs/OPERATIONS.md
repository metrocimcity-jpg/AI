# Operations

SiteGuard runs without a network connection after this machine has its Python packages, the frontend build, and the ONNX files.

## Install

```bat
run.bat
```

The API listens on `http://127.0.0.1:8000`. The dashboard dev server listens on `http://127.0.0.1:5173`. Copy `.env.example` to `.env` and change `SECRET_KEY` and `ADMIN_PASSWORD` before use. The default admin user is `admin` / `changeme` until you change it.

For a packaged UI, run `npm run build` inside `frontend`. FastAPI then serves `frontend/dist`.

## Models

Copy ONNX files into `models/` and set each `sha256` in `models/manifest.json`. A missing file is an error in `scripts/benchmark.py` and a logged skip in the live pipeline. The app does not download weights.

```bat
backend\.venv\Scripts\python scripts\benchmark.py --video samples\demo.avi
```

## Cameras

Add a camera from the Cameras page or `POST /api/cameras` with a file path, a USB index such as `0`, or an RTSP URL. File sources loop. Workers restart themselves if the thread exits.

## Faces

Leave face recognition off unless `face.enabled` is true. Enrollment requires the consent flag. Embeddings are encrypted with a key derived from `SECRET_KEY` and are not returned by the API. `DELETE /api/workers/faces` removes every biometric.

## Backup

Copy the `data/` directory. It holds `db.sqlite`, snapshots, and clips. Retention deletes rows and files older than `retention_days` (default 30). Run it immediately with `POST /api/retention/run`.

## Offline check

Unplug the network, open `/api/health`, and confirm `status` is `ok`. `python scripts/check_no_external_urls.py` fails if the UI references a public font or script host.
