import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.config import CACHE_TTL_SECONDS
from app.geo import MissionGeometry
from app.main import app
from app.providers import provider, region_cache_get, region_cache_key
from scripts.import_osm import import_region


def write_bundle(tmp_path, mission, network, **changes):
    payload = {
        "schema_version": 2,
        "source": "OpenStreetMap / Overpass",
        "attribution": "© OpenStreetMap contributors; ODbL 1.0",
        "complete": True,
        "boxes": MissionGeometry(mission).bounds(1000),
        "fetched_at": time.time() - 3600,
        "elements": network["elements"],
        **changes,
    }
    path = tmp_path / "region.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def test_cli_import_enables_analysis_without_provider_access(tmp_path, mission, network, monkeypatch):
    path, payload = write_bundle(tmp_path, mission, network)
    result = subprocess.run(
        [sys.executable, "-m", "scripts.import_osm", str(path)],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "STRAIGHTLINE_DATA_DIR": str(storage.DATA_DIR)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Imported OSM region: 3 features" in result.stdout

    async def must_not_download(*args, **kwargs):
        pytest.fail("An imported matching region must not make a provider request")

    monkeypatch.setattr(provider, "_overpass", must_not_download)
    with TestClient(app) as client:
        response = client.post("/api/missions/analyse", json=mission.model_dump())
    assert response.status_code == 200
    analysed = response.json()
    assert analysed["mission"]["max_deviation_m"] < 50
    assert analysed["data"]["cached"]
    assert analysed["data"]["feature_count"] == 3
    assert (
        analysed["data"]["fetched_at"]
        == datetime.fromtimestamp(payload["fetched_at"], timezone.utc).isoformat()
    )


def test_import_preserves_age_expiry_and_saved_missions(tmp_path, mission, network, monkeypatch):
    path, payload = write_bundle(tmp_path, mission, network)
    storage.save_mission({"id": "existing", "note": "preserve this saved mission"})
    count, fetched, imported = import_region(path)
    assert count == 3 and imported
    assert fetched == payload["fetched_at"]
    assert storage.load_mission("existing")["note"] == "preserve this saved mission"
    with storage.connection() as db:
        expiry, created = db.execute(
            "SELECT expires, created FROM cache WHERE key=?", (region_cache_key(payload["boxes"]),)
        ).fetchone()
    assert created == payload["fetched_at"]
    assert expiry == created + CACHE_TTL_SECONDS
    monkeypatch.setattr(storage.time, "time", lambda: expiry + 1)
    assert region_cache_get(payload["boxes"]) is None


def test_import_does_not_replace_newer_cached_data(tmp_path, mission, network):
    path, payload = write_bundle(tmp_path, mission, network)
    newer = time.time()
    storage.cache_put(
        region_cache_key(payload["boxes"]), {"elements": []}, CACHE_TTL_SECONDS, created_at=newer
    )
    assert import_region(path) == (0, newer, False)
    assert region_cache_get(payload["boxes"])[0]["elements"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 1},
        {"complete": False},
        {"fetched_at": 1},
        {"fetched_at": time.time() + 3600},
        {"boxes": [[91, 0, 92, 1]]},
        {"boxes": [[51.51, -0.1, 51.5, -0.09]]},
        {"boxes": [[-80, -180, 80, 180]]},
        {"boxes": [[float("nan"), -0.1, 51.51, -0.09]]},
        {"elements": [{"type": "way", "id": "invalid"}]},
        {"elements": [{"type": "relation", "id": 123}]},
        {"remark": "runtime error: timeout"},
    ],
)
def test_invalid_or_stale_bundles_do_not_write_cache(tmp_path, mission, network, changes):
    path, _ = write_bundle(tmp_path, mission, network, **changes)
    with pytest.raises(ValueError):
        import_region(path)
    with storage.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 0


def test_cache_keys_match_query_precision_across_projection_roundoff():
    boxes = [(51.50000001, -0.10000001, 51.51000001, -0.09000001)]
    equivalent = [(51.50000002, -0.10000002, 51.51000002, -0.09000002)]
    different = [(51.500002, -0.100002, 51.510002, -0.090002)]
    assert region_cache_key(boxes) == region_cache_key(equivalent)
    assert region_cache_key(boxes) != region_cache_key(different)


def test_legacy_region_cache_remains_available_and_newest_data_wins():
    import hashlib

    boxes = [(51.5, -0.1, 51.51, -0.09)]
    legacy = "osm:v2:" + hashlib.sha256(json.dumps(boxes, sort_keys=True).encode()).hexdigest()
    older = time.time() - 3600
    newer = time.time()
    storage.cache_put(legacy, {"elements": [{"id": 1}]}, CACHE_TTL_SECONDS, created_at=newer)
    assert region_cache_get(boxes)[1] == newer
    storage.cache_put(region_cache_key(boxes), {"elements": [{"id": 2}]}, CACHE_TTL_SECONDS, created_at=older)
    assert region_cache_get(boxes)[0]["elements"] == [{"id": 1}]
