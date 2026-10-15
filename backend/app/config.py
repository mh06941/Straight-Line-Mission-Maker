"""Explicit deployment limits; no provider credentials required."""

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("STRAIGHTLINE_DATA_DIR", "data"))
MAX_DISTANCE_M = float(os.getenv("MAX_MISSION_DISTANCE_M", "25000"))
MAX_QUERY_AREA_KM2 = float(os.getenv("MAX_QUERY_AREA_KM2", "400"))
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_URL = os.getenv("OVERPASS_URL", DEFAULT_OVERPASS_URL)
# A custom/dedicated provider must not silently send its queries to public mirrors.
# Set an empty fallback list to disable failover for the default provider too.
OVERPASS_FALLBACK_URLS = tuple(
    dict.fromkeys(
        url.strip()
        for url in os.getenv(
            "OVERPASS_FALLBACK_URLS",
            "https://overpass.private.coffee/api/interpreter" if OVERPASS_URL == DEFAULT_OVERPASS_URL else "",
        ).split(",")
        if url.strip() and url.strip() != OVERPASS_URL
    )
)
GEOCODE_URL = os.getenv("GEOCODE_URL", "https://nominatim.openstreetmap.org/search")
USER_AGENT = os.getenv(
    "OSM_USER_AGENT", "StraightLine/0.1 (local development; github.com/mh06941/Straight-Line-Mission-Maker)"
)
CACHE_TTL_SECONDS = int(os.getenv("OSM_CACHE_TTL_SECONDS", "86400"))
SAMPLE_STEP_M = 5.0
NUMERICAL_TOLERANCE_M = 0.5
