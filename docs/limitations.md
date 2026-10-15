# Scope, limitations and next work

The application implements the core planning vertical slice and bounded discovery. It does not establish safe passage or legal access.

## Current limits

- **Provider availability:** live Overpass, Nominatim and OSM tile connectivity was verified after initial cloud network denials. Providers can still throttle or fail; ideal geometry remains available independently. Offline fixtures are explicitly test-only and never serve as production fallbacks. See `validation.md` for the precise checks.
- **Terrain:** no DEM/elevation service is integrated. Profiles, gain/loss, slope, hillshade and terrain-derived difficulty are unavailable. Nothing is set to zero as a substitute.
- **OSM model:** way/node tags and shared node topology are supported. Mapped indoor passages are supported in relaxed mode, with entrance/opening-hour checks; building footprints alone do not establish a through route. Turn/access relations, complex multipolygons, multi-floor indoor routing, ferries, seasonal rules and comprehensive regional access law are not modelled. Directional footways are omitted. Strict mode can return no route even where real walking access exists.
- **Exploratory proposals:** relaxed mode can include short unverified road crossings, marked with orange dashes and on-site checks. These are bounded candidate links rather than recorded crossings, and may prove unusable. The target corridor remains unchanged when a best-effort route exceeds it. Manual waypoint editing and recording a verified shortcut through an unmapped building are not implemented.
- **Open spaces:** only small, explicitly supported closed polygons with bounded visible connections are considered. Links stay uncertain. Generic park/forest/agricultural land is never assumed traversable.
- **Barriers:** mapped barrier nodes and geometric fence/building/water/restriction intersections are conservatively filtered, with tagged bridge/tunnel/permission exceptions. Missing gates, incorrect layers and unmapped features still require independent inspection. The obstacle panel exposes ideal-line intersections, not every possible route hazard.
- **Bounds and snapping:** paths outside the downloaded/modelled region are not searched; disconnected results do not prove universal impossibility. Snapping never establishes access to a path. Routes can begin up to 100 m away from the requested points and gaps are shown separately.
- **Map poles:** backend geodesics and projections support the poles; the default OSM Web Mercator raster does not cover beyond ~85.05°. Antimeridian map lines are unwrapped. Strict RFC 7946 antimeridian-split MultiLineString export is future work; GPX normalises longitude.
- **Discovery:** rectangle-only, capped sampling with deterministic seed. It is not exhaustive. No polygon search, difficulty filter, DEM terrain preference or distributed worker queue. Surface preference applies to endpoint candidates, not every edge.
- **Persistence:** browser saves hold up to 50 parameter sets on that device. Backend mission records and cache use SQLite. There are no accounts, quotas, cross-device syncing or retention UI. Back up/manage the data directory for long-lived installations.
- **Internationalisation:** Unicode input, canonical SI storage and international coordinate calculations are implemented. English UI copy is not yet fully extracted into a translation catalog. Some advanced/custom controls expose explicit metres/kilometres even in imperial display mode.
- **Import/sharing:** no GPX import or short-link service. URLs encode only parameters; results depend on changing OSM data.
- **Scale:** one API process, two simultaneous analyses and one discovery job. Rate limits and job state are process-local. Public APIs are unsuitable as unlimited production infrastructure.

## Recommended priorities

1. Inspect generated routes against local access information and real-world conditions; expand geographically labelled regression fixtures.
2. Improve topology with directed edges, pedestrian restriction relations, barrier-crossing auditing, polygon holes and broader spatial indexing.
3. Add a documented/licensed global DEM source with explicit no-data and coverage handling; test elevation profiles and slope estimates.
4. Add persistent cancellable workers, region extracts/dedicated Overpass and production quotas before scaling.
5. Add GPX import, translation catalogs, complete imperial controls and stronger keyboard workflows for map drawing.
