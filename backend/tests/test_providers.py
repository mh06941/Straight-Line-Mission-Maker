import runpy

import httpx
import pytest

from app import config, providers
from app.providers import OSMProvider, ProviderError


@pytest.fixture(autouse=True)
def skip_provider_delays(monkeypatch):
    async def no_wait(_seconds):
        pass

    monkeypatch.setattr(providers.asyncio, "sleep", no_wait)


@pytest.fixture
def http_transport(monkeypatch):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(providers, "OVERPASS_URL", "https://primary.example/api/interpreter")
    monkeypatch.setattr(providers, "OVERPASS_FALLBACK_URLS", ("https://backup.example/api/interpreter",))

    def install(handler):
        monkeypatch.setattr(
            providers.httpx,
            "AsyncClient",
            lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
        )

    return install


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


@pytest.mark.parametrize("failure", ["timeout", "http_503", "invalid_json", "remark", "missing_elements"])
async def test_transient_primary_failure_uses_backup_and_caches_only_complete_data(http_transport, failure):
    requests = []
    expected = [{"type": "node", "id": 42, "lat": 51.5, "lon": -0.1}]

    def response(request):
        requests.append(request)
        if request.url.host == "backup.example":
            return httpx.Response(200, json={"elements": expected})
        if failure == "timeout":
            raise httpx.ReadTimeout("upstream timed out", request=request)
        if failure == "http_503":
            return httpx.Response(503)
        if failure == "invalid_json":
            return httpx.Response(200, text="temporarily unavailable")
        if failure == "remark":
            return httpx.Response(200, json={"elements": [], "remark": "runtime error: timeout"})
        return httpx.Response(200, json={"message": "incomplete"})

    http_transport(response)
    provider = OSMProvider()
    boxes = [(51.5, -0.1, 51.51, -0.09)]
    result = await provider.region(boxes)
    assert result["elements"] == expected
    assert not result["cached"]
    assert [request.url.host for request in requests] == ["primary.example", "backup.example"]
    assert requests[0].content == requests[1].content
    assert (await provider.region(boxes))["elements"] == expected
    assert (await provider.region(boxes))["cached"]
    assert len(requests) == 2


async def test_unavailable_mirrors_retry_primary_within_three_attempts(http_transport):
    hosts = []

    def response(request):
        hosts.append(request.url.host)
        return httpx.Response(504 if len(hosts) < 3 else 200, json={"elements": []})

    http_transport(response)
    result = await OSMProvider().region([(51.5, -0.1, 51.51, -0.09)])
    assert result["elements"] == []
    assert hosts == ["primary.example", "backup.example", "primary.example"]


async def test_exhausted_provider_failures_are_actionable_and_not_cached(http_transport, caplog):
    calls = []

    def response(request):
        calls.append(request.url.host)
        return httpx.Response(504 if len(calls) <= 3 else 200, json={"elements": []})

    http_transport(response)
    provider = OSMProvider()
    boxes = [(51.5, -0.1, 51.51, -0.09)]
    with pytest.raises(ProviderError, match="after 3 attempts.*HTTP 504.*backend terminal"):
        await provider.region(boxes)
    assert calls == ["primary.example", "backup.example", "primary.example"]
    assert "Overpass attempt 2/3 on backup.example" in caplog.text
    assert not (await provider.region(boxes))["cached"]
    assert len(calls) == 4


async def test_explicit_denial_does_not_retry_on_a_different_provider(http_transport):
    calls = []

    def response(request):
        calls.append(request.url.host)
        return httpx.Response(403)

    http_transport(response)
    with pytest.raises(ProviderError, match="denied.*HTTP 403"):
        await OSMProvider().region([(51.5, -0.1, 51.51, -0.09)])
    assert calls == ["primary.example"]


@pytest.mark.parametrize(
    ("url", "fallbacks", "expected"),
    [
        (None, None, ("https://overpass.private.coffee/api/interpreter",)),
        (None, "", ()),
        ("https://dedicated.example/api/interpreter", None, ()),
        (
            "https://dedicated.example/api/interpreter",
            " https://backup.example/api/interpreter, ,https://backup.example/api/interpreter,"
            "https://dedicated.example/api/interpreter",
            ("https://backup.example/api/interpreter",),
        ),
    ],
)
def test_fallback_configuration_respects_custom_provider_and_explicit_opt_out(
    monkeypatch, url, fallbacks, expected
):
    for name, value in (("OVERPASS_URL", url), ("OVERPASS_FALLBACK_URLS", fallbacks)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    settings = runpy.run_path(config.__file__)
    assert settings["OVERPASS_FALLBACK_URLS"] == expected
