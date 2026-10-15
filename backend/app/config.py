"""Explicit deployment limits; no provider credentials required."""

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("STRAIGHTLINE_DATA_DIR", "data"))
MAX_DISTANCE_M = float(os.getenv("MAX_MISSION_DISTANCE_M", "25000"))
MAX_QUERY_AREA_KM2 = float(os.getenv("MAX_QUERY_AREA_KM2", "400"))
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
GEOCODE_URL = os.getenv("GEOCODE_URL", "https://nominatim.openstreetmap.org/search")
USER_AGENT = os.getenv(
    "OSM_USER_AGENT", "StraightLine/0.1 (local development; github.com/mh06941/Straight-Line-Mission-Maker)"
)
CACHE_TTL_SECONDS = int(os.getenv("OSM_CACHE_TTL_SECONDS", "86400"))
SAMPLE_STEP_M = 5.0
NUMERICAL_TOLERANCE_M = 0.5
