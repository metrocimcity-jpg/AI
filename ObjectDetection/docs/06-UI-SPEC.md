# 06-UI-SPEC — Modern Dashboard

## 1. Design system
- **Look**: modern "control-room": dark default, subtle glassy cards, 12-col grid, 8-px spacing scale, 16-px card radius, soft borders (`border-white/10`), accent = construction **safety orange** `#F97316` + neutral slate; status colors: critical red, warning amber, info sky, ok emerald.
- **Type**: Inter (UI) + JetBrains Mono (numbers/IDs), self-hosted via `@fontsource`.
- **Components** (shadcn/ui): Card, Badge, Button, Tabs, Dialog/Sheet, DropdownMenu, Table, Tooltip, Toast (sonner), Switch, Slider, Select, Skeleton.
- **Motion**: 150–200 ms transitions; pulsing dot for live; flash border on critical alert; respect `prefers-reduced-motion`.
- **Responsive**: sidebar collapses < 1024 px; control-room wall mode (`/wall`) with kiosk fullscreen grid.
- **i18n-ready**: `react-i18next` with `en` (default) and room for `ar`/`fr` incl. RTL support.

## 2. Layout
Left sidebar (logo, nav, system status dot) · top bar (site name, clock, global search, alert bell with count, theme toggle, user menu) · content area.

Nav: **Dashboard · Live · Events · Analytics · Materials · Workers · Zones · Cameras · Settings**

## 3. Pages

### 3.1 Dashboard (`/`)
- KPI row: **People on site**, **PPE compliance %** (ring gauge), **Active alerts**, **Cameras online**, **Avg FPS / latency**.
- Main: featured live camera (with overlay toggle) + **Live alert feed** (right, newest first, severity chips, snapshot thumbnails, Ack button).
- Row: **Posture distribution** (donut: standing/walking/sitting/crouching/bending/lying/crawling), **PPE compliance trend** (area chart, 24 h), **Alerts by type** (bar).
- Row: **Materials on site** (cards with icon + count + sparkline: rebar, gypsum, cement bags, bricks...), **Zone occupancy** list.

### 3.2 Live (`/live`)
- Camera grid 1/2/4/6/9 layouts, click to focus. Per tile: name, FPS, status, record dot, people count, mini alert badge.
- Focus view: large video + canvas overlay; side panel with **tracked persons table** (ID, worker name, posture badge + duration, PPE icons ✅/⚠️/❔), toggles: boxes / skeleton / labels / zones / motion regions / materials.
- Overlay colors: green = compliant, red = violation, amber = unknown; lying/crawling get a pulsing red outline.
- Click a person → drawer with history timeline, face match, last snapshots.

### 3.3 Events (`/events`)
- Filter bar (date range, camera, type, severity, status, worker), virtualized table + card view, bulk acknowledge, detail drawer (snapshot, short clip, metadata JSON, timeline, resolve note), export CSV/PDF.

### 3.4 Analytics (`/analytics`)
- PPE compliance by camera/zone/hour heatmap, posture time distribution, incident trend, top violators (by worker if face enabled), shift comparison, motion heatmap per camera.

### 3.5 Materials (`/materials`)
- Inventory table: class, current count, 24 h change, last seen camera/zone, trend chart; filter by zone; "walkway obstruction" flags; CSV export.

### 3.6 Workers (`/workers`) *(face feature flag)*
- List + enrollment wizard (webcam capture/upload 3–5 photos, quality feedback), consent checkbox, authorized zones, attendance calendar, delete-all-biometrics button.

### 3.7 Zones (`/zones`)
- Select camera snapshot → draw/edit polygons on canvas (click to add points, drag handles), type, schedule, test-in-live preview.

### 3.8 Cameras (`/cameras`)
- Add/test connection (RTSP/USB/file), per-camera pipeline toggles & strides, thresholds sliders with live preview, status & diagnostics.

### 3.9 Settings (`/settings`)
- Models (list, license, version, reload, benchmark), runtime provider (CPU/CUDA/OpenVINO/TensorRT), alert rules editor, retention, users & roles, backup/restore, about/offline status ("No internet required ✓").

## 4. Key components
`KpiCard, PpeRing, PostureDonut, AlertFeed, AlertToast, CameraTile, VideoOverlayCanvas, PersonTable, PostureBadge, PpeIcons, MaterialCard, ZoneEditor, EventDrawer, FilterBar, SeverityBadge, EmptyState, ErrorBoundary, WsStatusIndicator`.

## 5. Behavior details
- WebSocket reconnect with exponential backoff; top bar shows "Live / Reconnecting".
- Audio alert (local bundled `.mp3`) for critical events, mutable, with browser autoplay-safe unlock.
- Optimistic UI for ack/resolve; toasts for failures.
- Skeleton loaders, empty states with call-to-action, error boundaries per card.
- All static assets bundled; verify `npm run build` output has **no external URLs** (add a CI check script `scripts/check_no_external_urls.sh`).
