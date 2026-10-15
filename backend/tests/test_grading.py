import math

import pytest

from app.analysis import analyse
from app.geo import MissionGeometry
from app.grading import grade_deviation
from tests.conftest import way


@pytest.mark.parametrize(
    "deviation,tier",
    [
        (0, "diamond"),
        (math.nextafter(10, 0), "diamond"),
        (10, "platinum"),
        (math.nextafter(25, 0), "platinum"),
        (25, "gold"),
        (math.nextafter(50, 0), "gold"),
        (50, "silver"),
        (math.nextafter(75, 0), "silver"),
        (75, "bronze"),
        (math.nextafter(100, 0), "bronze"),
        (100, "bronze"),
        (math.nextafter(100, math.inf), "out_of_grade"),
        (250, "out_of_grade"),
    ],
)
def test_exact_grade_boundaries_use_unrounded_metres(deviation, tier):
    grade = grade_deviation(deviation)
    assert grade["tier"] == tier
    assert grade["max_deviation_m"] == deviation


@pytest.mark.parametrize("deviation", [-1, math.inf, -math.inf, math.nan])
def test_invalid_deviation_has_no_grade(deviation):
    with pytest.raises(ValueError):
        grade_deviation(deviation)


def test_missing_deviation_is_ungraded():
    assert grade_deviation(None) is None


@pytest.mark.parametrize(
    "deviation,tier",
    [(5, "diamond"), (15, "platinum"), (35, "gold"), (65, "silver"), (90, "bronze"), (120, "out_of_grade")],
)
def test_analysis_grades_generated_route_independently_of_corridor(mission, deviation, tier):
    mission.max_deviation_m = 250
    geo = MissionGeometry(mission)
    coords = [geo.inverse.transform(x, y) for x, y in [(-500, 0), (0, deviation), (500, 0)]]
    data = {"elements": [way(1, [1, 2, 3], coords)], "fetched_at": 0, "cached": False}
    result = analyse(mission, data)
    assert result["status"] == "mapped"
    assert result["mission"]["corridor_compliant"]
    assert result["planned_grade"]["tier"] == tier
    assert result["planned_grade"]["max_deviation_m"] == result["mission"]["max_deviation_m"]


def test_no_route_and_missing_data_remain_ungraded(mission, network):
    mission.max_deviation_m = 10
    no_route = analyse(mission, network)
    assert no_route["walking"] is not None
    assert no_route["mission"] is None
    assert no_route["planned_grade"] is None
    assert analyse(mission, provider_error="Unavailable")["planned_grade"] is None
    assert analyse(mission, {"elements": [], "fetched_at": 0, "cached": False})["planned_grade"] is None


def test_uncertain_access_does_not_change_deviation_grade(mission, network):
    mission.strict = False
    for element in network["elements"][:2]:
        element["tags"] = {"highway": "path"}
    result = analyse(mission, network)
    assert result["status"] == "uncertain"
    assert result["planned_grade"]["tier"] == "gold"
