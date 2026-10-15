import pytest

from app.providers import OSMProvider, ProviderError


async def test_osm_cache_and_incomplete_response(monkeypatch):
    provider = OSMProvider()
    calls = []

    async def response(*args, **kwargs):
        calls.append(kwargs)
        return {"elements": []}

    monkeypatch.setattr(provider, "_request", response)
    boxes = [(51.5, -0.1, 51.51, -0.09)]
    assert not (await provider.region(boxes))["cached"]
    assert (await provider.region(boxes))["cached"]
    assert len(calls) == 1
    assert "[timeout:45]" in calls[0]["data"]["data"]

    async def incomplete(*args, **kwargs):
        return {"elements": [], "remark": "runtime error: timeout"}

    monkeypatch.setattr(provider, "_request", incomplete)
    provider.last_overpass = 0
    with pytest.raises(ProviderError, match="incomplete"):
        await provider.region([(52, 0, 52.01, 0.01)])


async def test_geocoder_cache(monkeypatch):
    provider = OSMProvider()
    calls = []

    async def response(*args, **kwargs):
        calls.append(kwargs)
        return [{"place_id": 1, "display_name": "京都市, 日本", "lat": "35.01", "lon": "135.76"}]

    monkeypatch.setattr(provider, "_request", response)
    first = await provider.geocode("京都市")
    assert first == await provider.geocode("京都市")
    assert first[0]["lat"] == 35.01
    assert len(calls) == 1


async def test_large_region_rejected_before_provider_access():
    provider = OSMProvider()
    with pytest.raises(ValueError, match="exceeds"):
        await provider.region([(-80, -180, 80, 180)])
