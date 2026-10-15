# Validation — 15 October 2026

This records observed results in the prepared cloud instance, not a claim that a new environment snapshot has been published or restored.

| Check | Observed result |
| --- | --- |
| Backend pytest | **120 passed**, no failures; one Starlette/httpx test-client deprecation warning |
| Ruff | Passed for application, tests and live-check script |
| Frontend Vitest | **9 passed** in three files |
| TypeScript + Vite production build | Passed; MapLibre and its module worker are bundled separately |
| Playwright desktop + mobile | **20 passed**: planning/analysis/grades/best-effort routing, line-following plaza/fountain detours, on-site checks and crossing proposals, saving/sharing/GPX export, global search/map selection/layers/help, discovery, and development startup/worker regressions |
| Production host API | Health, HTML root, OpenAPI docs, geodesic preview and real OSM analysis served successfully |
| Install repeatability | Executed the saved frozen uv/npm setup and build script successfully after initial installation; lockfiles unchanged |
| Docker Compose | Configuration validated |
| Python 3.13 image | Built successfully with TLS verification and the existing trusted proxy CA; non-root runtime started, health check became healthy, frontend/health/polar preview and SQLite write/read passed |

Offline geographical tests cover London, rural Wales, Swiss Alps, Adelaide, rural Canada, a boundary-region coordinate pair, antimeridian crossings and both polar regions. These deterministic cases test calculations and explicit synthetic topology/access cases; they do not claim physical verification in those places. Routing regressions include the bottleneck-versus-distance tradeoff, the two-pass tie case, internal edge curvature, retention beyond the target corridor, nonjoining mapped crossings, optional unverified crossings, indoor passages, locked gates, conditional access, open-space permissions and avoidance of mapped fence/building/water hazards.

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

A Windows user reported a blank page with `maplibre-gl.js does not provide an export named 'default'`. The first namespace-import/explicit-interop change passed ten local browser checks but did not resolve the user's report. Inspection of Vite's generated code explained why: it rewrites a namespace import into a default import for a CommonJS dependency.

The failure was reproduced in a browser by serving an optimized MapLibre module with named exports and no default export. React could not mount. The corrected frontend now loads the **installed UMD browser bundle as a local classic-script asset**, using MapLibre's browser global. There is no runtime package import through Vite's optimized module. Vite copies the script to a hashed production asset; there is no new CDN dependency, executable string evaluation or disabled verification. TypeScript imports remain type-only.

The production TypeScript/Vite build and all **14 desktop/mobile browser checks** passed after the browser-asset change. They include the missing-default-wrapper regression, cold/warm development startup with working map controls, an unavailable-WebGL fallback, and a failed map-script download with a usable planner and help. The six existing built-application workflows also passed. These checks ran in the Linux cloud browser; native Windows startup requires updating the complete checkout and restarting Vite. The README now includes fresh-clone instructions for users whose original folder was downloaded as a ZIP.

## Dependency advisory follow-up

The installed dependency audit reproduced the user's four findings: the MapLibre sanitizer advisory, a Vitest/@vitest/mocker file-read advisory, and the Tinypool advisory propagated through Vitest. MapLibre was upgraded to **6.14.0** and Vitest to **4.1.11**, updating the lockfile. Tinypool is no longer in the dependency tree. `npm audit --json` then reported **zero vulnerabilities**; no forced audit fix, ignored advisory or integrity bypass was used.

MapLibre 6's distribution is native ESM, replacing the intermediate UMD loader described above. The application lazily imports its named namespace without a default-export assumption, and Vite explicitly bundles its module worker and dependencies. This also retains the usable-planner fallback when the map download fails. The production build, seven frontend unit tests and **16 desktop/mobile browser checks** passed. The added worker check verifies messages are processed without worker errors in both development and production.

## Planned grading follow-up

The confirmed scale is Diamond `<10 m`, Platinum `<25 m`, Gold `<50 m`, Silver `<75 m`, Bronze `≤100 m`, then Out of grade. Backend tests exercise every exact cutoff and adjacent floating-point values, all six grades through real synthetic-network analysis, uncertain access, missing data and no-route outcomes. API checks cover the threshold endpoint, older saved analyses, discovery and GPX/GeoJSON/JSON metadata. Grading uses the unrounded generated mission maximum, independently of the selected corridor, and never assigns a grade to a missing mission route.

At the grading rollout, all **70 backend tests**, **7 frontend tests**, Ruff, the TypeScript/Vite production build and **16 desktop/mobile browser checks** passed. Browser workflows verified the Gold badge for the modelled 35.05 m fixture route, all six displayed thresholds, unchanged grades under imperial display, removal of the badge when a narrower corridor had no route, discovery badges and help guidance. The best-effort follow-up below supersedes the earlier narrow-corridor rejection behavior. The development fallback checks deliberately run without an API on port 8000; the threshold request fails there while the rest of the planner and help remain usable. Production workflows use the real test API on port 8001. Native Windows execution was not available in this cloud instance; the README requires updating and restarting both services for new API features.

## Best-effort routes and on-site checks

The user's shared Adelaide mission was reproduced with a bounded live OSM query containing **24,079 features**. Before this change, the shortest walking comparison reached **457.14 m** deviation; the minimax network route needed **266.61 m** and was discarded against the ±100 m setting.

The same captured real OSM data now produces a retained best-effort mission of **6,093.99 m**, maximum deviation **243.21 m**, **143.21 m** beyond the unchanged ±100 m target, graded **Out of grade**. Its 32 grouped checks comprise **7 proposed road crossings, 2 mapped indoor passages and 23 sections with uncertain access**. The result is an exploratory plan requiring on-site checks, not evidence that the whole route can be traversed. Recalculation with future map data may differ. No source data was edited to manufacture a closer route.

All **87 backend tests**, Ruff, **7 frontend tests**, the TypeScript/Vite build and **18 desktop/mobile browser checks** passed. Tests cover retaining and grading a route beyond target, optional crossing connections and their geometry/reasons, exclusion in strict mode, mapped indoor passages, obstacle/foot restrictions, grade separation, GPX verification waypoints and GeoJSON metadata. Browser checks locate a proposed crossing, verify the orange-dash legend, disable/re-enable proposals and export the best-effort mission. After the walking comparison was separated from proposed links, the two affected desktop/mobile flows were rerun and passed.

## Older API diagnostic

The screenshot's **Extra inputs are not permitted** error was reproduced by validating the current frontend payload against the preceding API schema: the rejected field was `allow_unverified_crossings`. The current API accepted the same Adelaide preview request with HTTP 200. The frontend now identifies this specific older-schema response and explains that the API must be restarted from the updated backend folder. It preserves ordinary validation errors and does not silently drop the crossing option. Regression checks cover both boolean values and continued rejection of genuinely unknown inputs. **89 backend tests**, **9 frontend tests**, Ruff and the TypeScript/Vite build passed for this follow-up.

## Victoria Square line-following correction

The next shared Adelaide mission was reproduced with **13,237 live OSM features**. Its initial mission had **195.73 m maximum deviation**, **61.47 m average deviation** and length **2,266.38 m**. Inspection found mapped crossing nodes tagged `barrier=kerb, kerb=lowered/flush` were incorrectly excluded. Separately, the previous distance tie-break allowed unnecessary local wandering when a larger bottleneck elsewhere fixed the maximum; open-space generation also omitted pedestrian plazas and parks lacking explicit access tags.

Mapped lowered/flush kerbs now preserve footway connectivity. Unknown kerbs remain on-site checks in relaxed mode, while restrictions/locked barriers still block. A passable kerb does not create an opening in an intersecting fence. Mission optimisation now minimises accumulated deviation after the primary maximum-deviation bound, with distance as a later tie-break. The open-space mesh adds ideal-line points and obstacle steering points, samples dense spaces, avoids fountain/water/road/rail/fence/building geometry, and identifies exploratory sections for verification. Polygon boundaries are no longer treated as mapped paths.

A final live query using the expanded fountain/pool selectors returned **13,246 features**. The corrected mission is **2,106.09 m** long, with **88.42 m maximum deviation** and **24.41 m average deviation**, within the original ±100 m target and graded **Bronze**. Maximum deviation across the southern Victoria Square comparison window fell from **69.83 m to 35.67 m**. No source mapping was edited to force this result; the data/geometry still require on-site verification.

Verification: **108 backend tests**, Ruff, **9 frontend tests**, TypeScript/Vite build and **20 desktop/mobile browser checks** passed. New regressions cover lowered/flush kerbs and explicit restrictions, unknown-kerb checks, minimax ties that prefer a longer/closer route, full-geometry deviation integration, parks/plazas without explicit access tags, dense polygons, a 25 km open-space mesh, fountain detours returning to the line, and exclusion of private/farmland/raised areas and complete fence/rail obstructions. Browser tests analyse and grade the real test API's synthetic plaza/fountain route and locate its verification section. Native Windows and physical access were not tested.

## Geographic-provider recovery

The shared Tea Tree Gully mission requests **22.44 km²**, below the configured query-area limit. Its exact query returned **8,103 live OSM features** from the primary Overpass endpoint in **36.5 seconds** during diagnosis. The public Private.coffee mirror returned HTTP 500 in the same check, so mirror availability is not assumed. The previous backend retried one endpoint three times and reduced connection, HTTP and JSON failures to the same generic message; the original failure on the user's Windows machine cannot be distinguished from that message alone.

Overpass now rotates configured endpoints within the existing three-attempt limit, keeps requests sequential, validates responses before caching, and logs the failed hostname and reason. Transient HTTP/network failures, invalid JSON and incomplete responses can recover through a mirror or a subsequent primary attempt. Explicit HTTP denials do not trigger mirror retries. A custom provider does not opt into public mirrors implicitly, and an empty fallback setting disables them.

The downloaded data produces a best-effort mission of **5,635.45 m**, with **165.94 m maximum deviation** and **48.61 m average deviation**. It remains outside the unchanged ±100 m target and is **Out of grade**. GPX/GeoJSON exports were parsed successfully; the GPX contains **322 track points** and **46 grouped on-site checks**. These are planning results from current mapping, not physical verification.

The updated analysis API was exercised with the exact shared parameters against the real primary provider: **HTTP 200**, a retained mission route and **8,103 features**, completing in **58.51 seconds** including analysis. Repeating the API request used the successful disk cache and returned the same route in **10.52 seconds**. No test fixture or synthetic geography was substituted for either request.

All **120 backend tests** and Ruff checks passed. Added regression cases cover timeout/HTTP/JSON/incomplete-response failover, identical queries across mirrors, caching only successful responses, bounded primary reattempts, actionable total failure, explicit denials and custom-provider/opt-out configuration. Frontend code and dependencies were unchanged; their preceding checks are recorded above.
