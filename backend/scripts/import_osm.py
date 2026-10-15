"""Import a downloaded StraightLine OSM region bundle into the local provider cache."""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import storage
from app.config import CACHE_TTL_SECONDS, MAX_QUERY_AREA_KM2
from app.geo import bbox_area
from app.providers import region_cache_get, region_cache_key

Finite = Annotated[float, Field(allow_inf_nan=False)]


class RegionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    source: Literal["OpenStreetMap / Overpass"]
    attribution: Literal["© OpenStreetMap contributors; ODbL 1.0"]
    complete: Literal[True]
    boxes: list[tuple[Finite, Finite, Finite, Finite]] = Field(min_length=1, max_length=2)
    fetched_at: Finite = Field(gt=0)
    elements: list[dict] = Field(max_length=60000)

    @field_validator("boxes")
    @classmethod
    def validate_bounds(cls, boxes):
        if any(not (-90 <= s < n <= 90 and -180 <= w < e <= 180) for s, w, n, e in boxes):
            raise ValueError("Each box must have valid south, west, north, east coordinates.")
        if bbox_area(boxes) > MAX_QUERY_AREA_KM2:
            raise ValueError("The downloaded region exceeds the configured query-area limit.")
        return boxes

    @field_validator("elements")
    @classmethod
    def validate_elements(cls, elements):
        if any(
            e.get("type") not in {"node", "way"} or type(e.get("id")) is not int or e["id"] <= 0
            for e in elements
        ):
            raise ValueError("Expected OSM nodes/ways with positive integer IDs.")
        return elements


def import_region(path):
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Region bundle exceeds the 64 MiB file limit.")
    bundle = RegionBundle.model_validate_json(path.read_text(encoding="utf-8-sig"))
    now = time.time()
    if bundle.fetched_at > now + 300:
        raise ValueError("The bundle's fetch time is in the future. Check the file and system clock.")
    if bundle.fetched_at + CACHE_TTL_SECONDS <= now:
        raise ValueError("The downloaded OSM data has expired. Download a fresh region bundle.")
    key = region_cache_key(bundle.boxes)
    existing = region_cache_get(bundle.boxes)
    if existing and existing[1] >= bundle.fetched_at:
        return len(existing[0]["elements"]), existing[1], False
    storage.cache_put(key, {"elements": bundle.elements}, CACHE_TTL_SECONDS, created_at=bundle.fetched_at)
    return len(bundle.elements), bundle.fetched_at, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Downloaded StraightLine OSM region JSON file")
    args = parser.parse_args()
    try:
        count, fetched, imported = import_region(args.bundle)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    action = "Imported" if imported else "Kept newer cached"
    stamp = datetime.fromtimestamp(fetched, timezone.utc).isoformat()
    print(f"{action} OSM region: {count:,} features; fetched {stamp}.")
    print("Select Analyse mission again with the same endpoints and corridor. No backend restart needed.")


if __name__ == "__main__":
    main()
