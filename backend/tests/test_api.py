from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from app import discovery, storage
from app.main import app
from app.providers import ProviderError, provider

client = TestClient(app)


def test_health_preview_validation(mission):
    assert client.get("/api/health").json()["status"] == "ok"
    preview = client.post("/api/missions/preview", json=mission.model_dump()).json()
    assert preview["distance_m"] == pytest.approx(1000)
    assert preview["ideal"]["type"] == "LineString"
    assert client.post("/api/missions/preview", json={"start": {"lat": 100, "lon": 0}}).status_code == 422


def test_analyse_persist_and_export(mission, network, monkeypatch):
    async def region(boxes):
        return network

    monkeypatch.setattr(provider, "region", region)
    response = client.post("/api/missions/analyse", json=mission.model_dump())
    assert response.status_code == 200
    result = response.json()
    assert result["mission"]["max_deviation_m"] < 50
    assert client.get(f"/api/missions/{result['id']}").json()["id"] == result["id"]
    gpx = client.get(f"/api/export/gpx/{result['id']}?route=mission")
    assert len(ElementTree.fromstring(gpx.content).findall(".//{*}trkpt")) > 2
    assert client.get(f"/api/export/geojson/{result['id']}").json()["geometry"]["type"] == "LineString"
    assert client.get(f"/api/export/summary/{result['id']}").json()["terrain"]["available"] is False


def test_provider_failure_retains_ideal_line(mission, monkeypatch):
    async def failed(boxes):
        raise ProviderError("Provider unavailable during this test")

    monkeypatch.setattr(provider, "region", failed)
    result = client.post("/api/missions/analyse", json=mission.model_dump()).json()
    assert result["status"] == "insufficient_data"
    assert result["ideal"]["coordinates"]
    assert result["walking"] is None
    assert "unavailable" in result["message"]


def test_cache_expiry(monkeypatch):
    storage.cache_put("test", {"ok": True}, 60)
    assert storage.cache_get("test")[0] == {"ok": True}
    storage.cache_put("expired", {}, -1)
    assert storage.cache_get("expired") is None


@pytest.mark.asyncio
async def test_discovery_and_cancellation(mission, network, monkeypatch):
    async def region(boxes):
        return network

    monkeypatch.setattr(provider, "region", region)
    request = discovery.DiscoveryRequest(
        west=-0.11, east=-0.07, south=51.49, north=51.51, min_length_m=100, max_length_m=2000
    )
    discovery.jobs.clear()
    job = discovery.new_job(request)
    await discovery.run_job(job, request)
    assert job["status"] == "complete"
    assert job["evaluated"] > 0
    assert job["results"]
    job2 = discovery.new_job(request)
    job2["status"] = "cancelled"
    await discovery.run_job(job2, request)
    assert job2["status"] == "cancelled"
    assert job2["evaluated"] == 0
    discovery.jobs.clear()
