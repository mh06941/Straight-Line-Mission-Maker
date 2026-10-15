import uuid
from datetime import datetime, timezone

from shapely.geometry import LineString, Point, Polygon, mapping

from .config import NUMERICAL_TOLERANCE_M
from .geo import MissionGeometry
from .routing import bottleneck, build_graph, route_stats, shortest_edges, snap_endpoint


def features_and_obstacles(elements, geo):
    features, obstacles = [], []
    walking_infrastructure = []
    for element in elements:
        tags = element.get("tags", {})
        if tags.get("bridge") not in (None, "no") or tags.get("highway") == "crossing":
            points = element.get("geometry", [])
            if len(points) >= 2:
                walking_infrastructure.append(geo.project([(p["lon"], p["lat"]) for p in points]))
    for element in elements:
        tags = element.get("tags", {})
        if element.get("type") == "node" and "lon" in element:
            coords = [(element["lon"], element["lat"])]
        else:
            coords = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
        if not coords:
            continue
        kind = None
        if tags.get("access") in {"private", "no", "permit"}:
            kind = "restricted"
        elif "building" in tags:
            kind = "building"
        elif "barrier" in tags:
            kind = "barrier"
        elif "waterway" in tags or tags.get("natural") in {"water", "wetland"}:
            kind = "water"
        elif "railway" in tags:
            kind = "railway"
        elif tags.get("highway") in {"primary", "secondary", "tertiary", "trunk", "motorway"}:
            kind = "road"
        elif "landuse" in tags or tags.get("leisure") == "park":
            kind = "landuse"
        elif "highway" in tags:
            kind = "pedestrian"
        if not kind:
            continue
        projected_coords = [geo.forward.transform(*p) for p in coords]
        closed = len(coords) >= 4 and coords[0] == coords[-1]
        area = closed and kind in {"building", "water", "landuse", "restricted"}
        geom = (
            Polygon(projected_coords)
            if area
            else (Point(projected_coords[0]) if len(coords) == 1 else LineString(projected_coords))
        )
        if not geom.is_valid:
            continue
        # Return only features close to the mission, keeping client payloads bounded.
        if geom.distance(geo.line) > 2500:
            continue
        safe_tags = {
            k: v
            for k, v in tags.items()
            if k
            in {
                "name",
                "highway",
                "access",
                "foot",
                "barrier",
                "building",
                "waterway",
                "landuse",
                "natural",
                "surface",
                "bridge",
                "tunnel",
                "locked",
            }
        }
        display_geom = (
            mapping(Point(geo.display_coords(coords)[0]))
            if len(coords) == 1
            else {
                "type": "Polygon" if area else "LineString",
                "coordinates": [geo.display_coords(coords)] if area else geo.display_coords(coords),
            }
        )
        features.append(
            {
                "type": "Feature",
                "geometry": display_geom,
                "properties": {"id": f"{element['type']}/{element['id']}", "kind": kind, **safe_tags},
            }
        )
        if kind in {"landuse", "pedestrian"}:
            continue
        # Point barriers within 1 m are relevant; other geometries must actually intersect.
        intersection = geo.line.intersection(geom.buffer(1) if isinstance(geom, Point) else geom)
        if intersection.is_empty:
            continue
        location = intersection.representative_point()
        position = geo.line.project(location)
        lon, lat = geo.inverse.transform(location.x, location.y)
        infrastructure = any(p.distance(location) < 25 for p in walking_infrastructure)
        obstacles.append(
            {
                "id": f"{element['type']}/{element['id']}",
                "kind": kind,
                "name": tags.get("name", kind.replace("_", " ").title()),
                "position_m": position,
                "crossing_extent_m": intersection.length,
                "coordinate": [lon, lat],
                "tags": safe_tags,
                "confidence": "mapped feature; physical obstruction unverified",
                "crossing_infrastructure_nearby": infrastructure,
            }
        )
    return {"type": "FeatureCollection", "features": features[:10000]}, sorted(
        obstacles, key=lambda o: o["position_m"]
    )


def analyse(request, data=None, provider_error=None):
    geo = MissionGeometry(request)
    result = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": request.model_dump(),
        **geo.preview(request.max_deviation_m),
        "walking": None,
        "mission": None,
        "minimum_corridor_m": None,
        "status": "insufficient_data",
        "message": "Insufficient data to assess feasibility.",
        "obstacles": [],
        "features": {"type": "FeatureCollection", "features": []},
        "terrain": {
            "available": False,
            "reason": "No elevation provider configured. Elevation, gradients and terrain difficulty are unknown.",
        },
        "difficulty": None,
        "numerical_tolerance_m": NUMERICAL_TOLERANCE_M,
        "warnings": [
            "Mapped routes do not establish current legal or physical access. Check local rules and conditions.",
            "Missing OSM features do not indicate unobstructed or accessible land.",
        ],
        "data": {
            "source": "OpenStreetMap / Overpass",
            "confidence": "unknown",
            "fetched_at": None,
            "cached": False,
        },
    }
    if provider_error:
        result["message"] = provider_error
        return result
    elements = data["elements"]
    result["data"].update(
        {
            "fetched_at": datetime.fromtimestamp(data["fetched_at"], timezone.utc).isoformat(),
            "cached": data["cached"],
            "feature_count": len(elements),
        }
    )
    result["features"], result["obstacles"] = features_and_obstacles(elements, geo)
    graph, counts = build_graph(elements, geo, request.strict)
    result["data"].update(
        {"network_nodes": graph.number_of_nodes(), "network_edges": graph.number_of_edges(), **counts}
    )
    result["data"]["confidence"] = (
        "limited" if graph.number_of_edges() < 20 else "mapped network present; completeness unknown"
    )
    result["data"]["assessment"] = (
        "Network density describes available evidence, not completeness, legal access or route feasibility. Relations and turn restrictions are not modelled."
    )
    if not graph.number_of_edges():
        result["message"] = (
            "No eligible pedestrian network found. Strict mode requires supporting foot-access tags; sparse mapping cannot establish feasibility."
        )
        return result
    start, start_snap = snap_endpoint(graph, geo.start.pair(), geo, "start")
    end, end_snap = snap_endpoint(graph, geo.end.pair(), geo, "end")
    result["snapping"] = {"start": start_snap, "end": end_snap}
    if start is None or end is None:
        result["message"] = (
            "No eligible mapped path within 100 m of one or both endpoints. Move the markers onto mapped paths."
        )
        return result
    if start == end:
        result["message"] = "Both endpoints snap to the same network location. Move the points farther apart."
        return result
    gaps = max(start_snap["distance_m"], end_snap["distance_m"])
    if gaps > 1:
        result["warnings"].append(
            "Routes begin/end at snapped path locations. Access across the displayed endpoint gaps is unassessed; these gaps are excluded from route statistics."
        )
    walking_edges = shortest_edges(graph, start, end)
    result["walking"] = route_stats(walking_edges, graph, geo)
    optimum = bottleneck(graph, start, end)
    result["minimum_corridor_m"] = optimum
    if optimum is None:
        result["status"] = "no_route"
        result["message"] = (
            "The eligible walking network is disconnected. No route found in the downloaded area; a route outside it may exist."
        )
        return result
    if optimum > request.max_deviation_m:
        result["status"] = "no_route"
        result["message"] = (
            f"No route within ±{request.max_deviation_m:g} m in the available network. Its minimum corridor is approximately ±{optimum:.1f} m. The corridor was not widened."
        )
        return result
    edges = shortest_edges(graph, start, end, optimum)
    route = route_stats(edges, graph, geo)
    result["mission"] = route
    result["status"] = "uncertain" if route["unverified_sections"] or gaps > 1 else "mapped"
    result["message"] = (
        "Route found within the corridor; access includes uncertain sections or endpoint gaps."
        if result["status"] == "uncertain"
        else "Route found within the corridor using mapped pedestrian access."
    )
    route["corridor_compliant"] = route["max_deviation_m"] <= request.max_deviation_m
    # Deliberately partial: no elevation input is converted into a fictitious easy terrain score.
    known_score = min(
        10,
        max(
            1,
            1
            + route["distance_m"] / 5000
            + len(result["obstacles"]) * 0.12
            + min(3, route["uncertain_distance_m"] / 250),
        ),
    )
    result["difficulty"] = {
        "score": round(known_score, 1),
        "complete": False,
        "explanation": "Partial planning score = 1 + distance/5 km + 0.12 × mapped intersections + min(3, uncertain metres/250), clamped to 1–10. Terrain and unmapped hazards are unknown.",
    }
    return result
