# Geographic model and routing

## Coordinates and accuracy

Canonical input/output coordinates are WGS84 latitude/longitude; GeoJSON uses longitude/latitude. PyProj's ellipsoidal `Geod` provides inverse/direct distance and bearings. The ideal reference is the finite shortest geodesic, densified to at most 25 m segments. Exported GPX longitude is normalised to −180…180; map geometry is unwrapped around the mission for date-line rendering.

Local operations use an **azimuthal equidistant projection centered on the geodesic midpoint**. The ideal geodesic passes through its center and becomes a straight radial segment. This avoids UTM zone discontinuities and supplies a metric CRS in polar regions. It is preferable here to choosing one UTM zone for a cross-zone mission. The default analysis cap is 25 km; do not assume the same distortion/error budget after increasing that limit. OSM's raster basemap is Web Mercator, with no coverage beyond approximately 85.05° latitude, although backend calculations support the poles.

Overpass queries use the envelope of the geodesic buffer. Date-line envelopes are split, and buffers containing a pole use a full-longitude cap. Query area is integrated on the WGS84 ellipsoid between parallels, avoiding zero-area polar boxes and underestimated large geographic rectangles.

## Access and topology

A direct Overpass-to-NetworkX adapter replaces OSMnx in this MVP: it retrieves obstacles and node-preserving walking geometry in one bounded request, keeps the access policy explicit, and avoids a second provider download. GeoPandas is unnecessary for the current geometry-sized operations; Shapely and PyProj supply them directly.

The graph is a NetworkX undirected multigraph built directly from Overpass way node IDs. Adjacent way nodes form edges; parallel ways remain distinct. A geometric crossing never becomes an intersection by proximity. Shared OSM nodes provide connectivity, preserving normal bridge/tunnel grade separation. OSM tagging errors remain possible. A Shapely spatial index also filters edges against mapped building/water/restricted interiors and fence/wall intersections; tagged bridges, tunnels, specific foot permissions and permitted gate locations provide conservative exceptions.

Explicit `foot=no/private` blocks an edge. Explicit foot permission can override general private vehicle/land access. `highway=footway/pedestrian/steps` supplies supporting pedestrian designation; generic `path` and roads without relevant access tags remain uncertain. Strict mode excludes uncertain edges. Conditional access and opening-hour tags remain uncertain because time-dependent evaluation is not implemented. Directional footways/conveying ways are conservatively omitted rather than routed against their restrictions. Locked or non-permitted barrier nodes remove adjacent edges. This intentionally sacrifices coverage rather than inventing legal rights.

Start and finish snap to the closest eligible edge within 100 m. That edge is split at the projected nearest point. **No access connector is invented**: the route begins at the snapped point; gap distance is displayed separately, and any gap above 1 m makes the whole mission status uncertain. Distance/deviation metrics cover only the generated path geometry.

Relaxed mode can add straight visibility edges between graph nodes inside closed park/common/recreation polygons with explicit access support. Links must remain entirely inside the polygon, be at most 250 m, and avoid mapped building, water, fence, railway, restriction and barrier geometry. At most 20 polygons with at most 60 eligible nodes each are considered. These edges are uncertain even when access tags support the surrounding space. Complex multipolygon relations are not interpreted as accessible open spaces.

## Bottleneck optimisation

Every edge's **full geometry** is geodesically densified at ≤5 m. Metric distance from every sample to the finite ideal geodesic is evaluated; the edge bottleneck uses its largest deviation plus a 0.05 m conservative guard. The UI reports a 0.5 m model numerical tolerance at the default local scale. This is a numerical modelling tolerance, not a positional accuracy claim about OSM or a proof about the physical path. Projected sampled segments approximate the tagged geodesic geometry; physical curvature not present in OSM cannot be recovered. Within a projected straight segment, distance to the reference segment is convex, so its maximum occurs at an endpoint. Sampling bounds curved projected geodesics, and the local cap controls distortion.

1. Bottleneck Dijkstra computes `b[v] = min(max(b[u], edge.deviation))`.
2. If the optimal bottleneck exceeds the user limit, **no mission route is returned**. The practical walking route can still be displayed and the smallest corridor in this finite graph is reported.
3. Otherwise a second shortest-path pass uses only edges at or below the optimal bottleneck (floating equality tolerance 1e−8 m). It minimises distance, then uncertain distance for exact distance ties.

A single lexicographic Dijkstra pass does not always minimise final distance among bottleneck ties: a shorter prefix with a larger intermediate bottleneck may become preferable once both prefixes encounter a larger shared edge. A deterministic regression test covers this case. A squared-deviation penalty is not used as a surrogate for minimax.

The conventional walking route uses shortest edge length in the same eligible network. Both route objectives operate on a finite local graph, not all possible real-world routes.

## Statistics and obstacles

Lengths use WGS84 geodesics. Average deviation integrates the trapezoidal sampled deviation weighted by travelled distance. Within-threshold percentages interpolate where sample deviations cross 10/25/50/100 m. OSM polyline curvature and access are only as complete as its mapping. Obstacle intersection positions and dimensions are local metric estimates. A road/water intersection remains a **mapped potential obstacle**, not a declaration of impassability. Possible crossing infrastructure within 25 m is labelled unverified.

Difficulty is explicitly partial: `clamp(1 + distance_m/5000 + 0.12*intersection_count + min(3, uncertain_m/250), 1, 10)`. Elevation, gradients, terrain risk and unmapped barriers are unknown. No score is issued when no mission route is found.

## Discovery

A ≤64 km² rectangle is downloaded once. Up to 100 mapped nodes are sampled deterministically, candidate pairs in the requested length range are shuffled, and at most 24 are analysed. Surface preference filters endpoint candidates by mapped tags; it does not constrain every intermediate segment or infer elevation. At most five UI results are retained (API supports ten). Ranking prefers mapped status, then lower bottleneck, fewer mapped intersections and shorter distance. Cancellation stops between bounded candidates; an in-flight provider request or CPU candidate may complete. Jobs are process-local and expire after one hour when a later search starts.
