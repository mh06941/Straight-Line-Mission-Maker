import networkx as nx
import pytest

from app.analysis import analyse
from app.geo import MissionGeometry
from app.routing import access_class, add_edge, bottleneck, build_graph, shortest_edges


def test_bottleneck_priority_over_length():
    graph = nx.MultiGraph()
    for a, b, length, deviation in [(0, 1, 1000, 5), (1, 3, 1000, 5), (0, 2, 10, 10), (2, 3, 10, 10)]:
        graph.add_edge(a, b, length=length, deviation=deviation, access="mapped")
    optimum = bottleneck(graph, 0, 3)
    route = shortest_edges(graph, 0, 3, optimum)
    assert optimum == 5
    assert sum(e[2]["length"] for e in route) == 2000


def test_second_pass_resolves_shared_bottleneck_distance_ties():
    # A single lexicographic Dijkstra label loses the shorter prefix at node 2.
    graph = nx.MultiGraph()
    for a, b, length, deviation in [(0, 1, 100, 1), (1, 2, 100, 1), (0, 2, 10, 5), (2, 3, 10, 10)]:
        graph.add_edge(a, b, length=length, deviation=deviation, access="mapped")
    optimum = bottleneck(graph, 0, 3)
    route = shortest_edges(graph, 0, 3, optimum)
    assert optimum == 10
    assert sum(e[2]["length"] for e in route) == 20


def test_inner_geometry_deviation_is_not_ignored(mission):
    geo = MissionGeometry(mission)
    coords = [geo.inverse.transform(x, y) for x, y in [(-500, 0), (0, 150), (500, 0)]]
    graph = nx.MultiGraph()
    add_edge(graph, 1, 2, coords, geo, access="mapped", tags={}, way_id=1)
    assert graph[1][2][0]["deviation"] == pytest.approx(150.05, abs=0.1)


def test_hard_corridor_and_obstacle_analysis(mission, network):
    result = analyse(mission, network)
    assert result["mission"]["corridor_compliant"]
    assert 35 <= result["mission"]["max_deviation_m"] < 36
    assert result["mission"]["average_deviation_m"] == pytest.approx(17.5, abs=0.2)
    assert 25 < result["mission"]["within_percent"]["10"] < 30
    assert result["obstacles"][0]["kind"] == "building"
    assert result["terrain"]["available"] is False
    mission.max_deviation_m = 10
    result = analyse(mission, network)
    assert result["status"] == "no_route"
    assert result["mission"] is None
    assert result["walking"] is not None
    assert result["max_deviation_m"] == 10


@pytest.mark.parametrize(
    "tags,expected",
    [
        ({"highway": "path"}, "uncertain"),
        ({"highway": "footway"}, "mapped"),
        ({"highway": "footway", "access": "private"}, "blocked"),
        ({"highway": "path", "foot": "yes", "access": "private"}, "mapped"),
        ({"highway": "path", "foot": "no"}, "blocked"),
    ],
)
def test_access_policy(tags, expected):
    assert access_class(tags) == expected


def test_crossing_geometries_do_not_join(mission):
    geo = MissionGeometry(mission)

    def way(identifier, nodes, points):
        return {
            "type": "way",
            "id": identifier,
            "nodes": nodes,
            "geometry": [dict(zip(("lon", "lat"), geo.inverse.transform(*p))) for p in points],
            "tags": {"highway": "footway"},
        }

    graph, _ = build_graph(
        [way(1, [1, 2], [(-500, 0), (500, 0)]), way(2, [3, 4], [(0, -500), (0, 500)])], geo
    )
    assert not nx.has_path(graph, 1, 3)


def test_sparse_data_is_not_feasible(mission):
    result = analyse(mission, {"elements": [], "fetched_at": 0, "cached": True})
    assert result["status"] == "insufficient_data"
    assert result["mission"] is None
    assert result["difficulty"] is None
