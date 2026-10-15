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
    if min(box[0] for box in boxes) > 51.525:
        plaza_geo = MissionGeometry(
            MissionRequest(start={"lat": 51.54, "lon": -0.1}, bearing=90, distance_m=1000)
        )

        def shape(identifier, nodes, points, tags):
            return {
                "type": "way",
                "id": identifier,
                "nodes": nodes,
                "geometry": [
                    {"lon": lon, "lat": lat}
                    for lon, lat in (plaza_geo.inverse.transform(*point) for point in points)
                ],
                "tags": tags,
            }

        return {
            "elements": [
                shape(
                    1,
                    [1, 2, 3, 4, 1],
                    [(-550, -80), (550, -80), (550, 80), (-550, 80), (-550, -80)],
                    {"highway": "pedestrian", "area": "yes", "name": "Browser test plaza"},
                ),
                shape(
                    2,
                    [5, 6, 7, 8, 5],
                    [(-15, -15), (15, -15), (15, 15), (-15, 15), (-15, -15)],
                    {"amenity": "fountain"},
                ),
            ],
            "fetched_at": time.time(),
            "cached": False,
        }
    if min(box[0] for box in boxes) > 51.505:
        crossing_geo = MissionGeometry(
            MissionRequest(start={"lat": 51.52, "lon": -0.1}, bearing=90, distance_m=1000)
        )

        def way(identifier, nodes, points, tags):
            return {
                "type": "way",
                "id": identifier,
                "nodes": nodes,
                "geometry": [
                    {"lon": lon, "lat": lat}
                    for lon, lat in (crossing_geo.inverse.transform(*point) for point in points)
                ],
                "tags": tags,
            }

        return {
            "elements": [
                way(1, [1, 2], [(-500, 0), (-10, 35)], {"highway": "footway"}),
                way(2, [3, 4], [(10, 35), (500, 0)], {"highway": "footway"}),
                way(
                    3,
                    [5, 6],
                    [(0, 10), (0, 60)],
                    {"highway": "primary", "foot": "yes", "name": "Browser test road"},
                ),
            ],
            "fetched_at": time.time(),
            "cached": False,
        }
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
