# Validation — 15 October 2026

This records observed results in the prepared cloud instance, not a claim that a new environment snapshot has been published or restored.

| Check | Observed result |
| --- | --- |
| Backend pytest | **43 passed**, no failures; one Starlette/httpx test-client deprecation warning |
| Ruff | Passed for application, tests and live-check script |
| Frontend Vitest | **7 passed** in two files |
| TypeScript + Vite production build | Passed; MapLibre separated into its own renderer chunk |
| Playwright desktop + mobile | **6 passed**: planning/analysis/hard corridor rejection, saving/sharing/GPX export, global search/map selection/layers/help, and bounded discovery/result selection |
| Production host API | Health, HTML root, OpenAPI docs, geodesic preview and real OSM analysis served successfully |
| Install repeatability | Executed the saved frozen uv/npm setup and build script successfully after initial installation; lockfiles unchanged |
| Docker Compose | Configuration validated |
| Python 3.13 image | Built successfully with TLS verification and the existing trusted proxy CA; non-root runtime started, health check became healthy, frontend/health/polar preview and SQLite write/read passed |

Offline geographical tests cover London, rural Wales, Swiss Alps, Adelaide, rural Canada, a boundary-region coordinate pair, antimeridian crossings and both polar regions. These deterministic cases test calculations and explicit synthetic topology/access cases; they do not claim physical verification in those places. Routing regressions include the bottleneck-versus-distance tradeoff, the two-pass tie case, internal edge curvature, hard corridor rejection, nonjoining geometric crossings, locked gates, conditional access, open-space permissions and avoidance of mapped fence/building/water hazards.

## Live provider results

Initial cloud requests received proxy HTTP 403. After the required network configuration was saved, subsequent requests succeeded; the runtime access change was independently verified. The draft save alone was not treated as proof of connectivity.

- Overpass status and bounded feature queries: successful.
- Nominatim status and actual `London` search: successful, three provider results.
- OSM raster tile request: HTTP 200 PNG.
- Live browser: real London analysis and 77 successful real tile responses. The headless browser does not inherit the cloud proxy, so the validation harness fetched those tiles through Node's existing proxy and trusted CA, then delivered the unchanged tile bytes to MapLibre. Production browser map requests remain direct to the documented provider endpoint. No TLS verification was disabled.

The optional script `uv run python -m scripts.live_smoke` fetches one bounded cached region per selected location and chooses eligible connected-network endpoints. The executed six-region run produced:

| Region | Real OSM features | Eligible edges | Outcome | Mission length | Maximum deviation |
| --- | ---: | ---: | --- | ---: | ---: |
| London | 5,728 | 5,551 | Mapped-access route found | 1,199.9 m | 249.9 m |
| Rural Wales | 981 | 306 | Mapped-access route found | 933.3 m | 167.4 m |
| Swiss Alps / Zermatt | 1,487 | 1,634 | Mapped-access route found | 1,191.9 m | 298.1 m |
| Adelaide | 3,832 | 2,547 | Mapped-access route found | 1,566.2 m | 214.4 m |
| Rural Canada | 1 | 0 | Insufficient pedestrian evidence | — | — |
| Basel border region | 1,754 | 859 | Mapped-access route found | 1,170.5 m | 124.3 m |

All generated routes in that run obeyed the selected ±1,000 m test corridor. A separate London browser/API check obeyed ±300 m. The Basel sample is a border-region check, not evidence that its selected endpoints lie in different countries. An arbitrary London endpoint pair also returned a disconnected strict network, demonstrating the no-route outcome. No corridor was expanded and no flat terrain or synthetic route was substituted.

To rerun selected live checks responsibly:

```bash
cd backend
uv run python -m scripts.live_smoke --region london
# Optional additional regions: wales, alps, adelaide, canada, border
```

Provider results change over time. These checks demonstrate ingestion, computation and UI integration; they do not establish current legal access, mapping completeness, terrain safety or physical traversability. Full terrain analysis, live polar routing, load testing and a new-task snapshot restoration were not performed. See [limitations](limitations.md).

## Development startup follow-up

A Windows user reported a blank page with `maplibre-gl.js does not provide an export named 'default'`. MapLibre's UMD entry was being consumed through an assumed default export. The frontend now uses a namespace import and declares MapLibre's dependency interop explicitly in Vite, so dependency scanning and serving use the same export handling.

The production TypeScript/Vite build and all **10 desktop/mobile browser checks** passed after this change. Four added checks exercise the actual Vite development server, page load/reload with dependency optimisation, map construction and controls, and a usable planner when WebGL is unavailable. The six existing built-application checks also passed. Validation ran in the Linux cloud browser; the user's Windows startup still requires pulling the fix, restarting Vite with `--force`, and refreshing the browser.
