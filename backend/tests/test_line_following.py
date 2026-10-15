import networkx as nx
import pytest
from shapely.geometry import Polygon

from app.analysis import analyse
from app.geo import MissionGeometry
from app.routing import add_edge, bottleneck, shortest_edges
from tests.conftest import way


def test_shared_maximum_does_not_allow_unnecessary_wandering():
    graph = nx.MultiGraph()
    # A shared final obstruction fixes the maximum. Before it, the closer
    # path is longer; the walking comparison and mission should differ.
    for a, b, length, maximum, integral in [
        (0, 1, 100, 40, 4000),
        (1, 3, 100, 40, 4000),
        (0, 2, 150, 2, 300),
        (2, 3, 150, 2, 300),
        (3, 4, 50, 80, 2000),
    ]:
        graph.add_edge(
            a, b, length=length, deviation=maximum, deviation_integral_m2=integral, access="mapped"
        )
    optimum = bottleneck(graph, 0, 4)
    assert optimum == 80
    walking = shortest_edges(graph, 0, 4, optimum)
    mission = shortest_edges(graph, 0, 4, optimum, prefer_line=True)
    assert [edge[1] for edge in walking] == [1, 3, 4]
    assert [edge[1] for edge in mission] == [2, 3, 4]
    assert max(edge[2]["deviation"] for edge in mission) == optimum


def test_deviation_integral_measures_full_geometry(mission):
    geo = MissionGeometry(mission)
    graph = nx.MultiGraph()
    coords = [geo.inverse.transform(x, y) for x, y in [(-500, 0), (0, 20), (500, 0)]]
    add_edge(graph, 1, 2, coords, geo, access="mapped", tags={}, way_id=1)
    edge = graph[1][2][0]
    assert edge["deviation_integral_m2"] / edge["length"] == pytest.approx(10, abs=0.01)


def open_space_data(mission, tags, obstacle=None):
    geo = MissionGeometry(mission)
    half_length = geo.distance / 2 + 50
    coords = [
        geo.inverse.transform(x, y)
        for x, y in [
            (-half_length, -80),
            (half_length, -80),
            (half_length, 80),
            (-half_length, 80),
            (-half_length, -80),
        ]
    ]
    elements = [way(1, [1, 2, 3, 4, 1], coords, **tags)]
    elements[0]["tags"] = tags
    if obstacle:
        points = (
            [(0, -100), (0, 100)]
            if obstacle in {"fence", "railway"}
            else [(-15, -15), (15, -15), (15, 15), (-15, 15), (-15, -15)]
        )
        obstacle_tags = (
            {"barrier": "fence"}
            if obstacle == "fence"
            else {"railway": "tram"}
            if obstacle == "railway"
            else {"amenity": "fountain"}
        )
        elements.append(
            {
                "type": "way",
                "id": 2,
                "geometry": [
                    {"lon": lon, "lat": lat}
                    for lon, lat in (geo.inverse.transform(*point) for point in points)
                ],
                "tags": obstacle_tags,
            }
        )
    return geo, {"elements": elements, "fetched_at": 0, "cached": False}


@pytest.mark.parametrize(
    "tags",
    [{"highway": "pedestrian", "area": "yes"}, {"highway": "footway", "area": "yes"}, {"leisure": "park"}],
)
def test_open_ground_stays_on_line_without_explicit_access_tag(mission, tags):
    mission.strict = False
    _, data = open_space_data(mission, tags)
    result = analyse(mission, data)
    assert result["mission"] is not None
    assert result["mission"]["max_deviation_m"] < 0.1
    assert result["mission"]["average_deviation_m"] < 0.01
    assert result["mission"]["verification_sections"][0]["kind"] == "open_space"
    assert result["walking"] is None


def test_fountain_detour_returns_to_line(mission):
    mission.strict = False
    geo, data = open_space_data(mission, {"highway": "pedestrian", "area": "yes"}, "fountain")
    result = analyse(mission, data)
    route = result["mission"]
    assert route is not None
    assert 15 < route["max_deviation_m"] < 25
    assert route["within_percent"]["10"] > 85
    projected = geo.project(route["geometry"]["coordinates"])
    assert not projected.intersects(Polygon([(-15, -15), (15, -15), (15, 15), (-15, 15)]))
    assert all(abs(y) < 0.1 for x, y in projected.coords if abs(x) > 100)


def test_dense_park_is_sampled_instead_of_discarded(mission):
    mission.strict = False
    geo, data = open_space_data(mission, {"leisure": "park", "access": "yes"})
    points = [geo.inverse.transform(-500 + index * 10, 40) for index in range(101)]
    data["elements"].append(way(3, list(range(100, 201)), points))
    result = analyse(mission, data)
    assert result["data"]["off_path_candidates"] > 0
    assert result["mission"]["max_deviation_m"] < 0.1


def test_long_open_space_keeps_a_connected_line_mesh(mission):
    mission.strict = False
    mission.distance_m = 25000
    _, data = open_space_data(mission, {"leisure": "park"})
    result = analyse(mission, data)
    assert result["mission"] is not None
    assert result["mission"]["distance_m"] == pytest.approx(25000, abs=0.1)
    assert result["mission"]["max_deviation_m"] < 0.1


@pytest.mark.parametrize("obstacle", ["fence", "railway"])
def test_open_space_mesh_cannot_cross_a_complete_obstruction(mission, obstacle):
    mission.strict = False
    _, data = open_space_data(mission, {"highway": "pedestrian", "area": "yes"}, obstacle)
    assert analyse(mission, data)["mission"] is None


@pytest.mark.parametrize(
    "tags",
    [
        {"leisure": "park", "access": "private"},
        {"leisure": "park", "foot": "no"},
        {"landuse": "farmland"},
        {"leisure": "park", "layer": "1"},
    ],
)
def test_open_mesh_requires_eligible_ground_and_respects_restrictions(mission, tags):
    mission.strict = False
    _, data = open_space_data(mission, tags)
    assert analyse(mission, data)["mission"] is None


@pytest.mark.parametrize("kerb", ["lowered", "flush", "no"])
def test_mapped_crossing_is_not_disconnected_by_passable_kerbs(mission, kerb):
    geo = MissionGeometry(mission)
    coords = [geo.inverse.transform(x, 0) for x in (-500, 0, 500)]
    data = {
        "elements": [
            way(1, [1, 2, 3], coords, footway="crossing"),
            {"type": "node", "id": 2, "tags": {"barrier": "kerb", "kerb": kerb}},
        ],
        "fetched_at": 0,
        "cached": False,
    }
    assert analyse(mission, data)["mission"] is not None
    data["elements"][1]["tags"]["foot"] = "no"
    assert analyse(mission, data)["mission"] is None


def test_unknown_kerb_is_a_check_in_relaxed_mode(mission):
    geo = MissionGeometry(mission)
    coords = [geo.inverse.transform(x, 0) for x in (-500, 0, 500)]
    data = {
        "elements": [way(1, [1, 2, 3], coords), {"type": "node", "id": 2, "tags": {"barrier": "kerb"}}],
        "fetched_at": 0,
        "cached": False,
    }
    assert analyse(mission, data)["mission"] is None
    mission.strict = False
    result = analyse(mission, data)
    assert result["mission"] is not None
    assert result["mission"]["verification_sections"][0]["kind"] == "barrier"


def test_passable_kerb_does_not_create_an_opening_in_a_fence(mission):
    geo = MissionGeometry(mission)
    coords = [geo.inverse.transform(x, 0) for x in (-500, 0, 500)]
    lon, lat = coords[1]
    fence = [geo.inverse.transform(0, y) for y in (-50, 50)]
    data = {
        "elements": [
            way(1, [1, 2, 3], coords),
            {"type": "node", "id": 2, "lon": lon, "lat": lat, "tags": {"barrier": "kerb", "kerb": "lowered"}},
            {
                "type": "way",
                "id": 3,
                "geometry": [{"lon": x, "lat": y} for x, y in fence],
                "tags": {"barrier": "fence"},
            },
        ],
        "fetched_at": 0,
        "cached": False,
    }
    assert analyse(mission, data)["mission"] is None
