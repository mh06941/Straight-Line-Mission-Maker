import time

import pytest

from app import storage
from app.geo import MissionGeometry
from app.models import MissionRequest


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)


def way(identifier, nodes, coords, **tags):
    return {
        "type": "way",
        "id": identifier,
        "nodes": nodes,
        "geometry": [{"lon": lon, "lat": lat} for lon, lat in coords],
        "tags": {"highway": "footway", **tags},
    }


@pytest.fixture
def mission():
    return MissionRequest(start={"lat": 51.5, "lon": -0.1}, bearing=90, distance_m=1000, max_deviation_m=50)


@pytest.fixture
def network(mission):
    geo = MissionGeometry(mission)

    def coord(x, y):
        return geo.inverse.transform(x - 500, y)

    elements = [
        way(1, [1, 2, 4], [coord(0, 0), coord(500, 35), coord(1000, 0)]),
        way(2, [1, 3, 4], [coord(0, 0), coord(500, 90), coord(1000, 0)]),
        {
            "type": "way",
            "id": 3,
            "geometry": [
                {"lon": x, "lat": y}
                for x, y in [
                    coord(480, -20),
                    coord(520, -20),
                    coord(520, 20),
                    coord(480, 20),
                    coord(480, -20),
                ]
            ],
            "tags": {"building": "yes"},
        },
    ]
    return {"elements": elements, "fetched_at": time.time(), "cached": False}
