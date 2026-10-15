import networkx as nx
import pytest

from app.analysis import analyse
from app.geo import MissionGeometry
from app.routing import build_graph
from tests.conftest import way


def crossing_network(mission, **road_tags):
    geo = MissionGeometry(mission)

    def coords(points):
        return [geo.inverse.transform(*point) for point in points]

    return [
        way(1, [1, 2], coords([(-500, 0), (-10, 0)])),
        way(2, [3, 4], coords([(10, 0), (500, 0)])),
        way(3, [5, 6], coords([(0, -50), (0, 50)]), highway="primary", foot="yes", **road_tags),
    ]


def test_crossing_proposals_are_optional_uncertain_and_locatable(mission):
    mission.strict = False
    elements = crossing_network(mission)
    data = {"elements": elements, "fetched_at": 0, "cached": False}
    result = analyse(mission, data)
    assert result["walking"] is None
    assert result["mission"]["corridor_compliant"]
    assert result["mission"]["access"] == "uncertain"
    checks = result["mission"]["verification_sections"]
    assert len(checks) == 1
    assert checks[0]["kind"] == "road_crossing"
    assert checks[0]["geometry"]["type"] == "LineString"
    assert len(checks[0]["coordinate"]) == 2
    assert checks[0]["distance_m"] == pytest.approx(20, abs=0.1)
    mission.allow_unverified_crossings = False
    assert analyse(mission, data)["mission"] is None
    mission.allow_unverified_crossings = True
    mission.strict = True
    assert analyse(mission, data)["mission"] is None


@pytest.mark.parametrize("hazard", ["building", "water", "waterway", "fence", "railway", "locked_gate"])
def test_crossing_proposals_respect_obstacles(mission, hazard):
    geo = MissionGeometry(mission)
    elements = crossing_network(mission)
    if hazard == "locked_gate":
        lon, lat = geo.inverse.transform(0, 0)
        elements.append(
            {"type": "node", "id": 10, "lon": lon, "lat": lat, "tags": {"barrier": "gate", "locked": "yes"}}
        )
    else:
        points = (
            [(0, -30), (0, 30)]
            if hazard in {"fence", "railway", "waterway"}
            else [(-5, -30), (5, -30), (5, 30), (-5, 30), (-5, -30)]
        )
        tags = (
            {"building": "yes"}
            if hazard == "building"
            else {"natural": "water"}
            if hazard == "water"
            else {"barrier": "fence"}
            if hazard == "fence"
            else {"waterway": "stream"}
            if hazard == "waterway"
            else {"railway": "tram"}
        )
        elements.append(
            {
                "type": "way",
                "id": 10,
                "geometry": [
                    {"lon": lon, "lat": lat}
                    for lon, lat in (geo.inverse.transform(*point) for point in points)
                ],
                "tags": tags,
            }
        )
    graph, _ = build_graph(elements, geo, False, allow_unverified_crossings=True)
    assert not nx.has_path(graph, 1, 4)


@pytest.mark.parametrize(
    "restriction",
    [
        {"bridge": "yes"},
        {"tunnel": "yes"},
        {"layer": "1"},
        {"level": "1"},
        {"access": "private", "foot": "no"},
        {"highway": "motorway"},
    ],
)
def test_crossing_proposals_do_not_connect_restricted_or_separated_roads(mission, restriction):
    geo = MissionGeometry(mission)
    elements = crossing_network(mission)
    elements[2]["tags"].update(restriction)
    graph, _ = build_graph(elements, geo, False, allow_unverified_crossings=True)
    assert not nx.has_path(graph, 1, 4)


@pytest.mark.parametrize(
    "passage_tags", [{"indoor": "yes"}, {"highway": "corridor"}, {"tunnel": "building_passage"}]
)
def test_mapped_indoor_passages_are_retained_for_verification(mission, passage_tags):
    mission.strict = False
    geo = MissionGeometry(mission)
    points = [geo.inverse.transform(x, 0) for x in (-500, 0, 500)]
    building = [
        geo.inverse.transform(x, y) for x, y in [(-30, -20), (30, -20), (30, 20), (-30, 20), (-30, -20)]
    ]
    path = way(1, [1, 2, 3], points, foot="yes")
    path["tags"].update(passage_tags)
    data = {
        "elements": [
            path,
            {
                "type": "way",
                "id": 2,
                "geometry": [{"lon": lon, "lat": lat} for lon, lat in building],
                "tags": {"building": "public", "access": "yes"},
            },
        ],
        "fetched_at": 0,
        "cached": False,
    }
    result = analyse(mission, data)
    assert result["mission"] is not None
    assert result["status"] == "uncertain"
    assert len(result["mission"]["verification_sections"]) == 1
    assert result["mission"]["verification_sections"][0]["kind"] == "indoor_passage"
    mission.strict = True
    assert analyse(mission, data)["mission"] is None
    mission.strict = False
    path["tags"]["foot"] = "no"
    assert analyse(mission, data)["mission"] is None
