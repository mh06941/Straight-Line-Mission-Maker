# Deployment notes

The tested local workflow is Python 3.12 + Node 24. The container was built with Python 3.13, which CI also targets. Python dependencies are pinned by `backend/uv.lock`; npm dependencies by `frontend/package-lock.json`. Keep signature, checksum and TLS verification enabled. There are no mandatory application credentials.

Build the frontend before starting FastAPI. Its static routes register when `frontend/dist` exists. The single-origin production arrangement avoids broad CORS configuration. Development CORS is limited to the two standard Vite loopback origins; Vite also proxies `/api`.

Use one Uvicorn worker until job state, request throttling and analysis limits move to shared infrastructure. Multiple workers would independently enforce provider quotas and cannot reliably poll/cancel each other's discovery jobs. Configure HTTPS, reverse-proxy request/connection/rate limits, CPU/memory caps, request-body limits, logs and monitoring before public access. The example container is non-root and exposes a health endpoint. Docker build/runtime validation is recorded separately in `validation.md`; its presence alone does not prove deployment readiness.

Provider policy requirements:

- **Nominatim:** server-side submitted searches, cached for seven days and serialized to at most one request per 1.1 seconds. No autocomplete. Set a meaningful identifying user agent and contact. If traffic grows, use a provider designed for that load or self-host.
- **Overpass:** bounded area, maxsize 32 MB and query timeout 45 s; HTTP timeout 65 s; max three attempts with backoff for transient failures. One request at a time with a 2 s interval. Responses with `remark` are rejected as incomplete. Cache expires after 24 hours by default.
- **OSM raster tiles:** normal interactive browser requests directly to the documented endpoint. Attribution is always displayed. No server proxy, bulk caching or prefetching. A public deployment must follow the tile usage policy or configure an appropriate licensed provider in `frontend/src/components/Map.tsx`.
- Default sources need `overpass-api.de`, `overpass.private.coffee` (fallback), `nominatim.openstreetmap.org` and `tile.openstreetmap.org`. Package installation also needs the usual PyPI/npm destinations.

SQLite stores cache and anonymous mission coordinates. Mission IDs are random UUIDs; they are not an account/authentication system. Do not store private trip details on a shared instance without a privacy and retention plan. Browser saves remain device-local. The production app never loads the synthetic provider in `backend/tests/offline_server.py`; the test server uses a separate storage directory.

The request model limits local mission length and deviation. The OSM model also limits feature counts and spatial extent. These caps are designed for small-scale use and should be load-tested before increasing. Provider success does not establish complete coverage or safe access.

In a TLS-inspecting build environment, the Dockerfile accepts an optional BuildKit secret named `build_ca` containing the trusted CA bundle. Supply existing proxy build arguments and resolve the proxy hostname through the supported network configuration. This preserves certificate verification; no insecure install flags are used and the CA mount does not become part of the image. The cloud validation build needed an explicit proxy-host mapping because Docker did not inherit the task host resolver.
