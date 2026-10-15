import pytest

from app.geo import GEOD, MissionGeometry, bbox_area
from app.models import MissionRequest


@pytest.mark.parametrize(
    "lat,lon",
    [
        (51.5, -0.1),
        (52.8, -3.8),
        (46.5, 8.0),
        (-34.9, 138.6),
        (56, -105),
        (49, 7),
        (85, 40),
        (-85, -100),
        (0, 179.99),
    ],
)
def test_global_geodesics(lat, lon):
    request = MissionRequest(start={"lat": lat, "lon": lon}, bearing=90, distance_m=5000)
    geo = MissionGeometry(request)
    assert geo.distance == pytest.approx(5000, abs=1e-5)
    assert geo.bearing == pytest.approx(90, abs=1e-6)
    assert geo.line.length == pytest.approx(5000, abs=0.01)
    assert geo.deviation(geo.center) < 1e-5
    point = geo.inverse.transform(0, 40)
    assert geo.deviation(point) == pytest.approx(40, abs=0.01)
    assert bbox_area(geo.bounds(1000)) < 100


def test_antimeridian_rendering_and_split_bounds():
    geo = MissionGeometry(MissionRequest(start={"lat": 0, "lon": 179.99}, end={"lat": 0, "lon": -179.99}))
    coordinates = geo.preview(50)["ideal"]["coordinates"]
    assert geo.distance < 2300
    assert max(abs(a[0] - b[0]) for a, b in zip(coordinates, coordinates[1:])) < 1
    assert len(geo.bounds(1000)) == 2
    assert all(-180 <= w < e <= 180 for _, w, _, e in geo.bounds(1000))


def test_distance_limits():
    with pytest.raises(ValueError, match="Mission length"):
        MissionGeometry(MissionRequest(start={"lat": 0, "lon": 0}, end={"lat": 0, "lon": 1}))
    with pytest.raises(ValueError):
        MissionRequest(start={"lat": 91, "lon": 0}, end={"lat": 0, "lon": 0})
    with pytest.raises(ValueError):
        MissionRequest(start={"lat": float("nan"), "lon": 0}, bearing=90, distance_m=1000)


def test_geodesic_known_reference():
    # Published WGS84 equatorial one-degree arc (not spherical haversine).
    assert GEOD.inv(0, 0, 1, 0)[2] == pytest.approx(111319.490793, abs=0.001)


def test_pole_crossing_query_does_not_collapse_to_zero_area():
    geo = MissionGeometry(MissionRequest(start={"lat": 89.99, "lon": 0}, bearing=0, distance_m=2000))
    boxes = geo.bounds(1000)
    assert boxes[0][1] == -180 and boxes[0][3] == 180
    assert boxes[0][2] == 90
    assert 1 < bbox_area(boxes) < 100
    assert bbox_area([(-90, -180, 90, 180)]) > 500_000_000


@pytest.mark.parametrize("length", [10, 25000])
def test_exact_distance_boundaries(length):
    geo = MissionGeometry(MissionRequest(start={"lat": -34, "lon": 138}, bearing=117, distance_m=length))
    assert geo.distance == pytest.approx(length, abs=1e-6)
