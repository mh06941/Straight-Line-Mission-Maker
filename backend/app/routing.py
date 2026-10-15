"""OSM topology and a two-pass bottleneck-then-distance optimizer.

Mapped ways connect through shared traversable OSM nodes. Relaxed mode can add
separately labelled, unverified road-crossing proposals between nearby paths.
Unknown access is admitted only in relaxed mode and is always identified.
"""

import heapq
import math

import networkx as nx
from shapely import STRtree
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points, unary_union

from .geo import GEOD, densify, geodesic_length

FOOT_HIGHWAYS = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "living_street",
    "track",
    "residential",
    "service",
    "unclassified",
    "tertiary",
    "secondary",
    "primary",
    "cycleway",
    "corridor",
}
PEDESTRIAN_WAYS = {"footway", "pedestrian", "path", "steps", "cycleway", "corridor"}
CROSSABLE_ROADS = {
    "residential",
    "service",
    "unclassified",
    "living_street",
    "tertiary",
    "secondary",
    "primary",
}
DENIED = {"no", "private", "customers", "delivery", "permit", "destination"}
EXPLICIT_FOOT = {"yes", "designated", "permissive", "official"}
PASSABLE = {
    "gate",
    "lift_gate",
    "swing_gate",
    "kissing_gate",
    "stile",
    "entrance",
    "bollard",
    "cycle_barrier",
}


def access_class(tags):
    if tags.get("foot") in DENIED:
        return "blocked"
    if tags.get("oneway:foot") in {"yes", "1", "-1"} or tags.get("conveying") not in {None, "no"}:
        # Omit directional pedestrian ways until a directed topology is supported.
        return "blocked"
    if any(key in tags for key in ("foot:conditional", "access:conditional", "opening_hours")):
        return "uncertain"
    if tags.get("foot") in EXPLICIT_FOOT:
        return "mapped"
    if tags.get("access") in DENIED or tags.get("highway") in {
        "motorway",
        "motorway_link",
        "trunk",
        "construction",
        "proposed",
    }:
        return "blocked"
    if tags.get("access") in {"yes", "permissive", "designated"} and tags.get("highway") in FOOT_HIGHWAYS:
        return "mapped"
    # A footway designation supports pedestrian use; a generic path does not establish legal access.
    if tags.get("highway") in {"footway", "pedestrian", "steps"}:
        return "mapped"
    return "uncertain"


def barrier_passable(tags):
    if tags.get("locked") == "yes" or tags.get("foot") in DENIED or tags.get("access") in DENIED:
        return False
    return tags.get("barrier") in PASSABLE and tags.get("foot") in EXPLICIT_FOOT


def add_edge(graph, a, b, coords, geo, *, access, tags, way_id, off_path=False):
    samples = densify(coords)
    length = geodesic_length(samples)
    if length <= 0:
        return
    deviation = max(geo.deviation(p) for p in samples) + 0.05
    graph.add_edge(
        a,
        b,
        length=length,
        deviation=deviation,
        coords=coords,
        access=access,
        tags=tags,
        way_id=way_id,
        off_path=off_path,
    )


def indoor_passage(tags):
    return tags.get("highway") in PEDESTRIAN_WAYS and (
        tags.get("indoor") == "yes"
        or tags.get("highway") == "corridor"
        or tags.get("tunnel") == "building_passage"
    )


def at_ground_level(tags):
    return (
        tags.get("bridge") in {None, "no"}
        and tags.get("tunnel") in {None, "no"}
        and tags.get("layer", "0") == "0"
        and tags.get("level", "0") == "0"
    )


def build_graph(elements, geo, strict=True, *, allow_unverified_crossings=False):
    graph = nx.MultiGraph()
    barriers = {
        e["id"]: e.get("tags", {})
        for e in elements
        if e.get("type") == "node" and "barrier" in e.get("tags", {})
    }
    excluded = 0
    query_envelope = geo.line.buffer(3000)
    hazards, hazard_kinds = [], []
    gate_buffers = []
    for element in elements:
        tags = element.get("tags", {})
        if element.get("type") == "node" and "lon" in element and barrier_passable(tags):
            gate_buffers.append(Point(geo.forward.transform(element["lon"], element["lat"])).buffer(2))
        coords = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
        if len(coords) < 2:
            continue
        closed = len(coords) >= 4 and coords[0] == coords[-1]
        kind = None
        if closed and tags.get("access") in DENIED:
            kind = "restricted"
        elif closed and tags.get("building") not in {None, "no"}:
            kind = "building"
        elif closed and tags.get("natural") == "water":
            kind = "water"
        elif tags.get("barrier") in {"fence", "wall", "hedge", "retaining_wall"}:
            kind = "barrier"
        if kind:
            line = geo.project(coords)
            shape = Polygon(line.coords) if closed and kind != "barrier" else line
            if shape.is_valid and query_envelope.intersects(shape):
                hazards.append(shape)
                hazard_kinds.append(kind)
    hazard_tree = STRtree(hazards)
    gates = unary_union(gate_buffers)
    for way in elements:
        tags = way.get("tags", {})
        if way.get("type") != "way" or tags.get("highway") not in FOOT_HIGHWAYS or "nodes" not in way:
            continue
        access = access_class(tags)
        passage = indoor_passage(tags)
        if passage and access != "blocked":
            access = "uncertain"
        if access == "blocked" or (strict and access != "mapped"):
            excluded += 1
            continue
        nodes, geometry = way["nodes"], way.get("geometry", [])
        if len(nodes) != len(geometry):
            continue
        for i, (a, b) in enumerate(zip(nodes, nodes[1:])):
            if (
                a in barriers
                and not barrier_passable(barriers[a])
                or b in barriers
                and not barrier_passable(barriers[b])
            ):
                continue
            coords = [(geometry[j]["lon"], geometry[j]["lat"]) for j in (i, i + 1)]
            # Full Overpass ways can extend beyond the query region. Keep the local model bounded.
            if not all(query_envelope.covers(Point(geo.forward.transform(*p))) for p in coords):
                continue
            segment = geo.project(coords)
            blocked = False
            for index in hazard_tree.query(segment, predicate="intersects"):
                kind, shape = hazard_kinds[index], hazards[index]
                if kind == "restricted" and tags.get("foot") in EXPLICIT_FOOT:
                    continue
                if kind == "water" and tags.get("bridge") not in {None, "no"}:
                    continue
                if kind == "building" and passage and not strict:
                    continue
                if kind in {"building", "barrier"} and tags.get("tunnel") not in {None, "no"}:
                    continue
                if kind == "barrier" and tags.get("bridge") not in {None, "no"}:
                    continue
                if kind == "barrier":
                    blocked = not segment.intersection(shape).difference(gates).is_empty
                else:
                    # Boundary-only contact is not entry into an obstacle polygon.
                    blocked = segment.intersection(shape.buffer(-0.25)).length > 0.1
                if blocked:
                    break
            if blocked:
                continue
            for node, coord in zip((a, b), coords):
                graph.add_node(node, coord=coord)
            add_edge(graph, a, b, coords, geo, access=access, tags=tags, way_id=way["id"])
    off_path_count = 0
    crossing_count = 0
    if not strict:
        off_path_count = add_open_space_connections(graph, elements, geo)
        if allow_unverified_crossings:
            crossing_count = add_road_crossing_proposals(graph, elements, geo, hazards)
    return graph, {
        "excluded_ways": excluded,
        "off_path_candidates": off_path_count,
        "unverified_crossing_candidates": crossing_count,
    }


def add_road_crossing_proposals(graph, elements, geo, hazards):
    """Short at-grade sidewalk-to-sidewalk proposals, explicitly requiring verification.

    This augments, rather than changes, OSM shared-node topology. It never infers
    a junction at a geometric crossing or a passage through a building footprint.
    """
    roads, names, blockers = [], [], list(hazards)
    for element in elements:
        tags = element.get("tags", {})
        if element.get("type") == "node":
            if "lon" in element and "barrier" in tags and not barrier_passable(tags):
                blockers.append(Point(geo.forward.transform(element["lon"], element["lat"])).buffer(2))
            continue
        coords = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
        if len(coords) < 2:
            continue
        line = geo.project(coords)
        if "railway" in tags and tags.get("railway") not in {"abandoned", "razed", "dismantled"}:
            blockers.append(line.buffer(2))
        if "waterway" in tags:
            blockers.append(line.buffer(1))
        if (
            tags.get("highway") in CROSSABLE_ROADS
            and access_class(tags) != "blocked"
            and at_ground_level(tags)
        ):
            roads.append(line)
            names.append(tags.get("name", "road"))
        elif "highway" in tags and (
            access_class(tags) == "blocked"
            or tags.get("highway") in {"motorway", "trunk", "motorway_link", "trunk_link"}
            or not at_ground_level(tags)
        ):
            blockers.append(line.buffer(1))
    if not roads:
        return 0
    road_tree, blocker_tree = STRtree(roads), STRtree(blockers)
    eligible = []
    for node, data in graph.nodes(data=True):
        edges = [edge for group in graph[node].values() for edge in group.values()]
        if not any(edge["tags"].get("highway") in PEDESTRIAN_WAYS for edge in edges):
            continue
        if any(not at_ground_level(edge["tags"]) or indoor_passage(edge["tags"]) for edge in edges):
            continue
        point = Point(geo.forward.transform(*data["coord"]))
        if not road_tree.query(point.buffer(60), predicate="intersects").size:
            continue
        eligible.append((node, point))
    eligible.sort(key=lambda item: (geo.line.distance(item[1]), str(item[0])))
    eligible = eligible[:4000]
    node_tree = STRtree([point for _, point in eligible])
    proposals = []
    for i, (a, point) in enumerate(eligible):
        for j in node_tree.query(point.buffer(60), predicate="intersects"):
            if j <= i:
                continue
            b, other = eligible[j]
            if graph.has_edge(a, b) or not 2 <= point.distance(other) <= 60:
                continue
            coords = [graph.nodes[a]["coord"], graph.nodes[b]["coord"]]
            link = geo.project(densify(coords, 5))
            crossings = road_tree.query(link, predicate="crosses")
            if not crossings.size or blocker_tree.query(link, predicate="intersects").size:
                continue
            proposals.append(
                (
                    max(geo.line.distance(point), geo.line.distance(other)),
                    link.length,
                    i,
                    int(j),
                    names[crossings[0]],
                )
            )
    proposals.sort()
    for _, _, i, j, name in proposals[:1000]:
        a, b = eligible[i][0], eligible[j][0]
        add_edge(
            graph,
            a,
            b,
            [graph.nodes[a]["coord"], graph.nodes[b]["coord"]],
            geo,
            access="uncertain",
            tags={"connection": "unverified_road_crossing", "name": f"Cross {name}"},
            way_id=None,
            off_path=True,
        )
    return min(len(proposals), 1000)


def add_open_space_connections(graph, elements, geo):
    """Bounded visibility edges inside explicitly accessible polygons, always uncertain.

    Multipolygon relations are deliberately not inferred from disconnected member ways.
    Fences/water/buildings/restricted polygons block links even inside public parks.
    """
    blockers = []
    spaces = []
    for element in elements:
        tags = element.get("tags", {})
        if element.get("type") == "node" and "barrier" in tags and not barrier_passable(tags):
            if "lon" in element:
                blockers.append(Point(geo.forward.transform(element["lon"], element["lat"])).buffer(2))
        coords = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
        if len(coords) < 2:
            continue
        projected = geo.project(coords)
        closed = len(coords) >= 4 and coords[0] == coords[-1]
        poly = Polygon(projected.coords) if closed else None
        if poly is not None and not poly.is_valid:
            continue
        if (
            (
                tags.get("leisure") in {"park", "common", "recreation_ground"}
                or tags.get("landuse") == "recreation_ground"
            )
            and closed
            and tags.get("foot") not in DENIED
        ):
            if tags.get("foot") in EXPLICIT_FOOT or tags.get("access") in {"yes", "permissive", "designated"}:
                if tags.get("access") not in DENIED or tags.get("foot") in EXPLICIT_FOOT:
                    spaces.append(poly)
        if (
            "building" in tags
            or "barrier" in tags
            or "waterway" in tags
            or tags.get("natural") == "water"
            or tags.get("access") in DENIED
            or "railway" in tags
        ):
            blockers.append(poly if poly is not None else projected.buffer(1))
    additions = 0
    for space in spaces[:20]:
        inside = [
            (n, d["coord"])
            for n, d in graph.nodes(data=True)
            if space.covers(Point(geo.forward.transform(*d["coord"])))
        ]
        # Refuse undersampled large spaces rather than creating arbitrary cross-country links.
        if len(inside) > 60:
            continue
        for i, (a, ca) in enumerate(inside):
            for b, cb in inside[i + 1 :]:
                link = geo.project(densify([ca, cb], 10))
                if (
                    link.length > 250
                    or not space.covers(link)
                    or any(link.intersects(obstacle) for obstacle in blockers)
                ):
                    continue
                add_edge(
                    graph,
                    a,
                    b,
                    [ca, cb],
                    geo,
                    access="uncertain",
                    tags={"connection": "open_space"},
                    way_id=None,
                    off_path=True,
                )
                additions += 1
    return additions


def snap_endpoint(graph, coordinate, geo, name):
    """Split the nearest edge; report the unassessed gap, without inventing an access link."""
    target = Point(geo.forward.transform(*coordinate))
    closest = None
    for a, b, key, data in list(graph.edges(keys=True, data=True)):
        line = geo.project(densify(data["coords"], 10))
        distance = target.distance(line)
        if closest is None or distance < closest[0]:
            closest = (distance, a, b, key, data, line)
    if closest is None or closest[0] > 100:
        return None, None
    distance, a, b, key, data, line = closest
    point = nearest_points(target, line)[1]
    coord = geo.inverse.transform(point.x, point.y)
    for node in (a, b):
        if GEOD.inv(*graph.nodes[node]["coord"], *coord)[2] < 0.1:
            return node, {"distance_m": distance, "coordinate": list(graph.nodes[node]["coord"])}
    graph.remove_edge(a, b, key)
    graph.add_node(name, coord=coord)
    add_edge(
        graph,
        a,
        name,
        [graph.nodes[a]["coord"], coord],
        geo,
        access=data["access"],
        tags=data["tags"],
        way_id=data["way_id"],
        off_path=data["off_path"],
    )
    add_edge(
        graph,
        name,
        b,
        [coord, graph.nodes[b]["coord"]],
        geo,
        access=data["access"],
        tags=data["tags"],
        way_id=data["way_id"],
        off_path=data["off_path"],
    )
    return name, {"distance_m": distance, "coordinate": list(coord)}


def bottleneck(graph, start, end):
    """First minimize max edge deviation. A second pass resolves distance ties globally."""
    values = {start: 0.0}
    serial = 0
    queue = [(0.0, serial, start)]
    while queue:
        value, _, node = heapq.heappop(queue)
        if value != values.get(node):
            continue
        if node == end:
            return value
        for neighbor, edges in graph[node].items():
            weight = min(edge["deviation"] for edge in edges.values())
            candidate = max(value, weight)
            if candidate < values.get(neighbor, math.inf):
                values[neighbor] = candidate
                serial += 1
                heapq.heappush(queue, (candidate, serial, neighbor))
    return None


def shortest_edges(graph, start, end, max_deviation=math.inf, *, include_proposals=True):
    # Minimize length first, then uncertain length, within the optimal bottleneck subgraph.
    best = {start: (0.0, 0.0)}
    previous = {}
    queue = [(0.0, 0.0, 0, start)]
    serial = 0
    while queue:
        length, uncertain, _, node = heapq.heappop(queue)
        if (length, uncertain) != best.get(node):
            continue
        if node == end:
            route = []
            while node != start:
                parent, key = previous[node]
                route.append((parent, node, graph[parent][node][key]))
                node = parent
            return route[::-1]
        for neighbor, edges in graph[node].items():
            for key, edge in edges.items():
                if not include_proposals and edge.get("off_path"):
                    continue
                if edge["deviation"] > max_deviation + 1e-8:
                    continue
                candidate = (
                    length + edge["length"],
                    uncertain + (edge["length"] if edge["access"] != "mapped" else 0),
                )
                if candidate < best.get(neighbor, (math.inf, math.inf)):
                    best[neighbor] = candidate
                    previous[neighbor] = (node, key)
                    serial += 1
                    heapq.heappush(queue, (*candidate, serial, neighbor))
    return None


def route_stats(edges, graph, geo):
    if edges is None:
        return None
    coords, uncertain_m, unverified, surfaces = [], 0.0, 0, set()
    checks, previous_check = [], None
    for a, _, data in edges:
        segment = data["coords"]
        if GEOD.inv(*graph.nodes[a]["coord"], *segment[0])[2] > 0.1:
            segment = segment[::-1]
        coords.extend(segment if not coords else segment[1:])
        if data["access"] != "mapped":
            uncertain_m += data["length"]
            unverified += 1
            tags = data["tags"]
            connection = tags.get("connection")
            if connection == "unverified_road_crossing":
                kind, reason = (
                    "road_crossing",
                    "Proposed crossing: check the crossing point, median and barriers on site.",
                )
            elif indoor_passage(tags):
                kind, reason = (
                    "indoor_passage",
                    "Check entrances, opening hours and whether through passage is available.",
                )
            elif connection == "open_space":
                kind, reason = (
                    "open_space",
                    "Proposed open-space link: confirm the ground and passage on site.",
                )
            else:
                kind, reason = (
                    "access_unknown",
                    "Pedestrian access or conditions are not fully established by the map tags.",
                )
            name = tags.get(
                "name",
                {"indoor_passage": "Indoor passage", "open_space": "Open-space connection"}.get(
                    kind, "Mapped path"
                ),
            )
            signature = (data["way_id"], kind, name)
            if previous_check == signature:
                checks[-1]["coords"].extend(segment[1:])
                checks[-1]["distance_m"] += data["length"]
            else:
                checks.append(
                    {
                        "id": f"check-{len(checks) + 1}",
                        "kind": kind,
                        "name": name,
                        "reason": reason,
                        "coords": list(segment),
                        "distance_m": data["length"],
                    }
                )
            previous_check = signature
        else:
            previous_check = None
        if data["tags"].get("surface"):
            surfaces.add(data["tags"]["surface"])
    if len(coords) < 2:
        return None
    samples = densify(coords)
    deviations = [geo.deviation(p) for p in samples]
    total = average = 0.0
    within = {t: 0.0 for t in (10, 25, 50, 100)}
    for a, b, da, db in zip(samples, samples[1:], deviations, deviations[1:]):
        length = GEOD.inv(*a, *b)[2]
        total += length
        average += (da + db) / 2 * length
        for threshold in within:
            if max(da, db) <= threshold:
                fraction = 1
            elif min(da, db) >= threshold:
                fraction = 0
            else:
                fraction = (threshold - min(da, db)) / abs(db - da)
            within[threshold] += length * fraction
    for check in checks:
        points = geo.display_coords(densify(check.pop("coords"), 25))
        check["geometry"] = {"type": "LineString", "coordinates": points}
        check["coordinate"] = points[len(points) // 2]
    return {
        "geometry": {"type": "LineString", "coordinates": geo.display_coords(densify(coords, 25))},
        "distance_m": total,
        "extra_distance_m": total - geo.distance,
        "max_deviation_m": max((e[2]["deviation"] for e in edges), default=0),
        "average_deviation_m": average / total if total else 0,
        "within_percent": {str(t): 100 * length / total if total else 0 for t, length in within.items()},
        "uncertain_distance_m": uncertain_m,
        "unverified_sections": unverified,
        "verification_sections": checks,
        "access": "uncertain" if unverified else "mapped",
        "surfaces": sorted(surfaces),
    }
