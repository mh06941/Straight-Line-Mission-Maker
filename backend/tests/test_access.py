import networkx as nx
import pytest

from app.geo import MissionGeometry
from app.routing import access_class, build_graph


def geometry(geo, points):
    return [{"lon": lon, "lat": lat} for lon, lat in (geo.inverse.transform(*p) for p in points)]


def test_locked_gate_removes_adjacent_edges(mission):
    geo = MissionGeometry(mission)
    elements = [
        {
            "type": "way",
            "id": 1,
            "nodes": [1, 2, 3],
            "geometry": geometry(geo, [(-100, 0), (0, 0), (100, 0)]),
            "tags": {"highway": "footway"},
        },
        {"type": "node", "id": 2, "tags": {"barrier": "gate", "foot": "yes", "locked": "yes"}},
    ]
    graph, _ = build_graph(elements, geo)
    assert graph.number_of_edges() == 0


@pytest.mark.parametrize(
    "permission,blocker,connected", [(True, False, True), (False, False, True), (True, True, False)]
)
def test_open_space_proposals_allow_missing_access_and_avoid_obstacles(
    mission, permission, blocker, connected
):
    geo = MissionGeometry(mission)
    elements = [
        {
            "type": "way",
            "id": 1,
            "nodes": [1, 2],
            "geometry": geometry(geo, [(-200, 0), (-50, 0)]),
            "tags": {"highway": "footway"},
        },
        {
            "type": "way",
            "id": 2,
            "nodes": [3, 4],
            "geometry": geometry(geo, [(50, 0), (200, 0)]),
            "tags": {"highway": "footway"},
        },
        {
            "type": "way",
            "id": 3,
            "geometry": geometry(geo, [(-60, -50), (60, -50), (60, 50), (-60, 50), (-60, -50)]),
            "tags": {"leisure": "park", **({"access": "yes"} if permission else {})},
        },
    ]
    if blocker:
        elements.append(
            {
                "type": "way",
                "id": 4,
                "geometry": geometry(geo, [(0, -60), (0, 60)]),
                "tags": {"barrier": "fence"},
            }
        )
    graph, _ = build_graph(elements, geo, strict=False)
    assert nx.has_path(graph, 1, 4) == connected
    if connected:
        assert graph[2][3][0]["access"] == "uncertain"
        assert graph[2][3][0]["off_path"]


def test_conditional_and_directional_ways_are_not_confirmed():
    assert access_class({"highway": "footway", "foot:conditional": "no @ (sunset-sunrise)"}) == "uncertain"
    assert access_class({"highway": "footway", "oneway:foot": "yes"}) == "blocked"


@pytest.mark.parametrize(
    "hazard,bridge,expected",
    [("water", False, 0), ("water", True, 1), ("building", False, 0), ("barrier", False, 0)],
)
def test_mapped_paths_cannot_silently_cross_hazards(mission, hazard, bridge, expected):
    geo = MissionGeometry(mission)
    hazard_tags = (
        {"natural": "water"} if hazard == "water" else {hazard: "fence" if hazard == "barrier" else "yes"}
    )
    points = (
        [(0, -40), (0, 40)]
        if hazard == "barrier"
        else [(-10, -40), (10, -40), (10, 40), (-10, 40), (-10, -40)]
    )
    elements = [
        {
            "type": "way",
            "id": 1,
            "nodes": [1, 2],
            "geometry": geometry(geo, [(-100, 0), (100, 0)]),
            "tags": {"highway": "footway", **({"bridge": "yes"} if bridge else {})},
        },
        {"type": "way", "id": 2, "geometry": geometry(geo, points), "tags": hazard_tags},
    ]
    graph, _ = build_graph(elements, geo)
    assert graph.number_of_edges() == expected
