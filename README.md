# StraightLine

**Find your own way.** A working global straight-line mission planner, with a React/MapLibre map and a FastAPI GIS backend. No registration or paid API account is required.

Choose endpoints or a bearing and distance, preview a WGS84 geodesic and deviation corridor, retrieve real OpenStreetMap data, and compare shortest walking and minimum-maximum-deviation routes. Results explicitly distinguish mapped access, uncertain sections, disconnected networks, and insufficient evidence.

## What works

- Worldwide map, submitted location search (including Unicode) and direct latitude/longitude search.
- Map clicks, draggable start/finish markers, coordinate fields, bearing/distance mode, metric/imperial display.
- Accurate WGS84 distances/bearings; densified ideal geodesic; route-centered metric projection that crosses UTM zones and supports polar and antimeridian calculations.
- Bounded Overpass retrieval with disk caching, serialization, rate limiting, retries, timeouts and provider-failure messages. No synthetic production-data fallback.
- OSM-node-based pedestrian topology; access filtering, conservative barrier handling, edge snapping with explicitly unassessed endpoint gaps.
- Two-pass bottleneck routing: smallest modelled maximum deviation, followed by shortest distance and access-confidence tie-breaking. The requested corridor is a hard limit and is never expanded automatically.
- Relaxed routing admits uncertain paths and bounded visibility connections inside explicitly accessible open-space polygons, avoiding mapped obstacles. These links remain unverified.
- Mapped obstacle intersections, feature layers, distance-weighted deviation statistics, corridor percentages and partial difficulty with an explicit formula.
- Bounded discovery in a map-drawn rectangle: one regional query, up to 24 candidate lines, ranked results, progress and cancellation.
- Local saved mission parameters, parameter-based share URLs, GPX/GeoJSON exports and downloadable JSON summaries.
- Responsive desktop sidebar/mobile sheet, accessible dialogs, helpful loading/error states, OpenAPI docs and automated tests.

Terrain elevation is **unavailable**, not assumed flat. Advanced terrain, GPX import, polygon discovery and accounts are future work. See [limitations and priorities](docs/limitations.md).

## Run locally — macOS / Linux

Prerequisites: **Python 3.12 or 3.13**, **uv 0.12.23+**, and **Node.js 24 LTS** (Node 22.12+ also satisfies Vite). Install uv using its [official instructions](https://docs.astral.sh/uv/getting-started/installation/).

```bash
cd Straight-Line-Mission-Maker/backend
uv sync --frozen
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd Straight-Line-Mission-Maker/frontend
npm ci
npm run dev
```

Open the Vite development server shown in your terminal. It forwards `/api` to port 8000. FastAPI's interactive API documentation is at `/docs` on port 8000.

Optional configuration: copy `.env.example` to `.env` at the repository root, edit it, and start the API from `backend/` with `uv run uvicorn app.main:app --reload --env-file ../.env`. Configuration is read at process startup. The file is ignored by Git. Set an identifying `OSM_USER_AGENT` with your deployment contact for public use.

## Windows PowerShell

Install Python, Node.js and uv first, then use two PowerShell terminals:

```powershell
Set-Location Straight-Line-Mission-Maker\backend
uv sync --frozen
uv run uvicorn app.main:app --reload --port 8000
```

```powershell
Set-Location Straight-Line-Mission-Maker\frontend
npm ci
npm run dev
```

Optional settings: `Copy-Item .env.example .env` from the repository root. uv manages the virtual environment; manual activation is unnecessary.

If the frontend is blank with a MapLibre `default`-export error, install the current code rather than changing the import alone. The patched MapLibre 6 engine uses native named ESM exports with a separately bundled module worker; it does not assume a default export. A map-load failure shows a message while leaving the planner usable.

For an existing Git checkout, stop the frontend, run `git pull origin main`, and restart with `npm run dev -- --force`. If the folder was downloaded as a ZIP, it is not a Git checkout. With Git installed, create a fresh clone in a separate folder:

```powershell
# Stop the frontend with Ctrl+C first. The existing backend can keep running.
Set-Location $env:USERPROFILE
git clone https://github.com/mh06941/Straight-Line-Mission-Maker.git StraightLine-updated
Set-Location StraightLine-updated\frontend
npm ci
npm run dev -- --force
```

Use the Local address printed by Vite and hard-refresh with Ctrl+Shift+R. Subsequent updates can use `git pull origin main` from this clone. When restarting the backend later, run `uv sync --frozen` and the API startup command from the new clone's `backend` directory.

## Try a mission

1. Search a place and submit, or enter `latitude, longitude`. Search moves the map; it does not choose a mission endpoint.
2. Open **Plan a mission**, press a crosshair and click the map. Choose the finish the same way, or switch to bearing/distance.
3. Choose maximum deviation **on each side** of the ideal line. Preview and ideal-line exports work without OSM connectivity.
4. Select **Analyse mission**. Strict mode requires supporting pedestrian tags; generic unclassified access is omitted. Turning strict mode off includes uncertain ways and eligible open-space links.
5. Inspect **Overview**, **Obstacles**, and **Data & access**. Snapped endpoint gaps are outside the route geometry and statistics; check them independently.
6. Save, share or export. Browser saves retain parameters, not a promise that a route will remain accessible.

Discovery: zoom into a small area, open **Discover**, and click two rectangle corners. Keep the area below 64 km². Public API work is bounded; a search is a candidate sample, not exhaustive optimisation.

## Verification

```bash
cd backend
uv run ruff check app tests
uv run pytest -q
cd ../frontend
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests start an **explicit test-only API on port 8001** using deterministic OSM-shaped fixtures in `backend/tests/offline_server.py`; they never replace production providers. They exercise the actual FastAPI analysis/routing and built React application. Test storage is isolated from production data. Tile requests are deliberately blocked during offline browser tests. Both desktop and mobile run the flows.

For an existing Chromium installation (as in this cloud machine):

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm run test:e2e
```

PowerShell equivalent: `$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE = "C:\path\to\chrome.exe"` before running the command.

Cloud writable-cache overrides, if home caches are read-only: `UV_CACHE_DIR=/workspace/.cache/uv` and `npm ci --cache /workspace/.cache/npm`. These are machine-specific; they are not necessary on a normal workstation.

## Structure

```text
backend/app/
  main.py          FastAPI endpoints, exports, built frontend serving
  models.py        validated requests
  geo.py           WGS84 geodesics, local projection, corridor and bounding boxes
  providers.py     public providers, throttling, retries and cache use
  routing.py       topology, access, snapping and two-pass minimax routing
  analysis.py      obstacle intersections, metrics and uncertainty
  discovery.py     bounded background jobs and ranking
  storage.py       SQLite provider cache and mission records
backend/tests/     deterministic geographical, API and routing tests
frontend/src/      React application, map, planning, statistics and browser storage
frontend/e2e/      desktop/mobile browser integration tests
docs/              algorithms, limitations, deployment and validation evidence
```

## Configuration and providers

| Variable | Default | Purpose |
| --- | --- | --- |
| `OSM_USER_AGENT` | StraightLine project identifier | Identify requests; use a deployment contact for production |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | OSM feature/network data |
| `GEOCODE_URL` | `https://nominatim.openstreetmap.org/search` | Submit-only geocoding; no autocomplete |
| `STRAIGHTLINE_DATA_DIR` | `data`, relative to backend working directory | SQLite cache and anonymous mission records |
| `OSM_CACHE_TTL_SECONDS` | `86400` | Provider cache freshness |
| `MAX_MISSION_DISTANCE_M` | `25000` | Local analysis distance limit; larger values need projection/performance validation |
| `MAX_QUERY_AREA_KM2` | `400` | Maximum Overpass box area; discovery has a stricter 64 km² cap |

Required network destinations: `overpass-api.de`, `nominatim.openstreetmap.org`, and `tile.openstreetmap.org` (browser). Dependencies use PyPI and npm. The default map uses the documented OSM raster endpoint; there is no satellite endpoint or secret API key. Respect [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/), [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/), and [Overpass resource guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html). No bulk tile downloads or offline tile prefetching are implemented.

Geographic data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under ODbL. Exported derivative geographic datasets may carry ODbL obligations. App code does not include a separate open-source license grant yet; the repository owner should choose one before third-party redistribution.

## Build and deployment

```bash
cd frontend
npm ci
npm run build
cd ../backend
uv sync --frozen --no-dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

FastAPI serves the built frontend and API from one origin. Build before starting the API; static routes are registered at startup. Alternatively: `docker compose up --build` from the repository root. The container uses Python 3.13, a non-root user and a persistent data volume.

The provided Compose configuration is a starting point for a small deployment. Read [deployment guidance](docs/deployment.md) before exposing it publicly. Public providers are shared infrastructure, not a scalable production routing backend.
