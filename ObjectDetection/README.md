# SiteGuard Vision — Offline Construction-Site AI Dashboard

Spec pack for **Cursor Desktop AI**. Open this folder as the project root in Cursor.

## What gets built
A fully **offline** (no internet at runtime) web dashboard + backend that analyses camera/video feeds on construction sites:

- **Human detection + posture**: standing, walking, sitting, crouching, bending, lying, crawling, climbing
- **PPE / safety**: helmet, vest, gloves, boots, goggles, harness (and the *missing* versions)
- **Site materials & machinery**: rebar bars, gypsum boards/packets, cement bags, bricks, pipes, plywood, steel beams, excavator, truck, forklift...
- **Motion detection** with zones (restricted areas, after-hours)
- **Face recognition** (offline, enrolled workers only)
- **Events/alerts** (no helmet, person lying = possible fall, intrusion, unknown face, ...)

## Folder map
```
.cursor/rules/           Always-on rules Cursor reads automatically
  00-project.mdc         Goals, stack, hard constraints (offline!)
  10-backend.mdc         Python/FastAPI conventions
  20-frontend.mdc        React/TS/Tailwind conventions
  30-ml.mdc              Model, inference, and posture-logic rules
docs/
  01-PRD.md              Product requirements
  02-ARCHITECTURE.md     Pipeline, modules, folder layout, data flow
  03-MODELS.md           Model choices, licenses, alternatives, export
  04-CLASSES-AND-RULES.md  Class taxonomy, posture logic, alert rules
  05-API-SPEC.md         REST + WebSocket contract, DB schema
  06-UI-SPEC.md          Dashboard pages, components, design system
  07-OFFLINE-DEPLOYMENT.md  Air-gapped install, hardware, packaging
  08-TASKS.md            Phased build prompts for Cursor (START HERE)
```

## How to use in Cursor
1. Open the folder in Cursor. The `.cursor/rules/*.mdc` files load automatically.
2. Open `docs/08-TASKS.md` and run the phases **in order** (one phase per Agent/Composer chat).
3. In each chat, attach context with `@docs/02-ARCHITECTURE.md` and the doc the phase names.
4. Do not skip the acceptance checks at the end of each phase.

## Run the app

From this folder:

```bat
run.bat
```

Sign in at `http://127.0.0.1:5173` (default `admin` / `changeme` until `.env` changes it). Open `http://127.0.0.1:5173/?mock=1` to walk the dashboard with sample data and no camera. Copy ONNX files into `models/` before live detection. See `docs/OPERATIONS.md`.

## Important licensing note
Ultralytics YOLO is **AGPL-3.0** (commercial license available), and InsightFace's pretrained models are **non-commercial**. If this is a commercial product, use the permissive alternatives listed in `docs/03-MODELS.md` (RT-DETR/YOLOX/RF-DETR + YuNet/SFace) or buy the proper licenses.
