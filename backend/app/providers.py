"""Bounded, cached and serialized public-service requests."""

import asyncio
import hashlib
import json
import time

import httpx

from . import storage
from .config import CACHE_TTL_SECONDS, GEOCODE_URL, MAX_QUERY_AREA_KM2, OVERPASS_URL, USER_AGENT
from .geo import bbox_area


class ProviderError(Exception):
    pass


class OSMProvider:
    def __init__(self):
        self.overpass_lock = asyncio.Lock()
        self.geocode_lock = asyncio.Lock()
        self.last_overpass = 0.0
        self.last_geocode = 0.0

    async def _request(self, url, *, method="GET", **kwargs):
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(65, connect=15), headers={"User-Agent": USER_AGENT}
                ) as client:
                    response = await client.request(method, url, **kwargs)
                if response.status_code in (429, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as error:
                if (
                    isinstance(error, httpx.HTTPStatusError)
                    and error.response.status_code < 500
                    and error.response.status_code != 429
                ):
                    raise ProviderError(
                        f"Geographic provider denied the request (HTTP {error.response.status_code}). Check service/network policy."
                    ) from error
                if attempt == 2:
                    raise ProviderError(
                        "Geographic provider is unavailable or timed out. Your ideal line is still available; retry later."
                    ) from error
                await asyncio.sleep(2**attempt)

    async def region(self, boxes):
        if bbox_area(boxes) > MAX_QUERY_AREA_KM2:
            raise ValueError(
                f"Requested OSM area exceeds {MAX_QUERY_AREA_KM2:g} km². Shorten the mission or narrow the search."
            )
        # Versioned selector set: older cached regions may lack plaza fountains/pools.
        key = "osm:v2:" + hashlib.sha256(json.dumps(boxes, sort_keys=True).encode()).hexdigest()
        hit = storage.cache_get(key)
        if hit:
            return {"elements": hit[0]["elements"], "fetched_at": hit[1], "cached": True}
        async with self.overpass_lock:
            hit = storage.cache_get(key)
            if hit:
                return {"elements": hit[0]["elements"], "fetched_at": hit[1], "cached": True}
            await asyncio.sleep(max(0, 2 - (time.monotonic() - self.last_overpass)))
            parts = []
            # Fetch node IDs and way geometry together, preserving topology and barrier nodes.
            for s, w, n, e in boxes:
                box = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
                for selector in (
                    "way[highway]",
                    "way[building]",
                    "way[barrier]",
                    "way[waterway]",
                    "way[natural=water]",
                    "way[landuse]",
                    "way[leisure=park]",
                    "way[amenity=fountain]",
                    "way[leisure=swimming_pool]",
                    "way[railway]",
                    "way[access]",
                    "node[barrier]",
                ):
                    parts.append(selector + box + ";")
            query = "[out:json][timeout:45][maxsize:32000000];(" + "".join(parts) + ");out body geom;"
            try:
                data = await self._request(OVERPASS_URL, method="POST", data={"data": query})
            finally:
                self.last_overpass = time.monotonic()
            if "remark" in data:
                raise ProviderError(
                    "OSM query was incomplete or exceeded provider limits. Try a smaller area."
                )
            elements = data.get("elements")
            if not isinstance(elements, list) or len(elements) > 60000:
                raise ProviderError("OSM response is too large or incomplete. Try a smaller area.")
            fetched = storage.cache_put(key, {"elements": elements}, CACHE_TTL_SECONDS)
            return {"elements": elements, "fetched_at": fetched, "cached": False}

    async def geocode(self, query):
        key = "geocode:" + query.casefold().strip()
        hit = storage.cache_get(key)
        if hit:
            return hit[0]
        async with self.geocode_lock:
            hit = storage.cache_get(key)
            if hit:
                return hit[0]
            await asyncio.sleep(max(0, 1.1 - (time.monotonic() - self.last_geocode)))
            try:
                data = await self._request(GEOCODE_URL, params={"q": query, "format": "jsonv2", "limit": 5})
            finally:
                self.last_geocode = time.monotonic()
            results = [
                {
                    "id": str(p["place_id"]),
                    "label": p["display_name"],
                    "lat": float(p["lat"]),
                    "lon": float(p["lon"]),
                }
                for p in data
            ]
            storage.cache_put(key, results, 7 * 86400)
            return results


provider = OSMProvider()
