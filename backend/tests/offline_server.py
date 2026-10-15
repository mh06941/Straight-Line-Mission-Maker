"""Browser-test server ONLY. Deterministic OSM-shaped data never enters the production app.

Run from backend: uv run python tests/offline_server.py
"""

import time

import uvicorn

from app.geo import MissionGeometry
from app.main import app
from app.models import MissionRequest
from app.providers import provider

geo = MissionGeometry(MissionRequest(start={"lat": 51.5, "lon": -0.1}, bearing=90, distance_m=1000))


async def region(boxes):
    points = [geo.inverse.transform(x, y) for x, y in [(-500, 0), (0, 35), (500, 0)]]
    return {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "nodes": [1, 2, 3],
                "geometry": [{"lon": lon, "lat": lat} for lon, lat in points],
                "tags": {"highway": "footway", "foot": "yes", "name": "Synthetic test path"},
            }
        ],
        "fetched_at": time.time(),
        "cached": False,
    }


async def geocode(query):
    return [{"id": "test", "label": "London (offline browser fixture)", "lat": 51.5, "lon": -0.1}]


provider.region = region
provider.geocode = geocode
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
