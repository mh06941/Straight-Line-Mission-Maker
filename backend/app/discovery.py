import asyncio
import random
import time
import uuid

from . import storage
from .analysis import analyse
from .geo import GEOD, bbox_area
from .models import DiscoveryRequest, MissionRequest
from .providers import provider

jobs = {}
MAX_CANDIDATES = 24


def search_boxes(request):
    if request.west < request.east:
        return [(request.south, request.west, request.north, request.east)]
    return [
        (request.south, request.west, request.north, 180),
        (request.south, -180, request.north, request.east),
    ]


def new_job(request: DiscoveryRequest):
    # Evict old terminal jobs, and cap active CPU/provider work.
    now = time.time()
    for key in list(jobs):
        if jobs[key]["status"] in {"complete", "failed", "cancelled"} and now - jobs[key]["created"] > 3600:
            del jobs[key]
    if sum(j["status"] in {"queued", "running"} for j in jobs.values()) >= 1:
        raise ValueError("A discovery search is already running. Wait or cancel it first.")
    if bbox_area(search_boxes(request)) > 64:
        raise ValueError("Discovery area must be at most 64 km². Zoom in and choose a smaller rectangle.")
    job = {
        "id": str(uuid.uuid4()),
        "created": now,
        "status": "queued",
        "progress": 0,
        "evaluated": 0,
        "candidate_limit": MAX_CANDIDATES,
        "results": [],
        "message": "Downloading one shared OSM region.",
    }
    jobs[job["id"]] = job
    return job


async def run_job(job, request):
    try:
        if job["status"] == "cancelled":
            return
        job["status"] = "running"
        data = await provider.region(search_boxes(request))
        nodes = {}
        for way in data["elements"]:
            tags = way.get("tags", {})
            if "highway" not in tags:
                continue
            if request.terrain == "paved" and tags.get("surface") not in {
                "asphalt",
                "paved",
                "concrete",
                "paving_stones",
            }:
                continue
            if request.terrain == "trail" and tags.get("highway") not in {"path", "track", "footway"}:
                continue
            for node, point in zip(way.get("nodes", []), way.get("geometry", [])):
                lon, lat = point["lon"], point["lat"]
                in_lon = (
                    request.west <= lon <= request.east
                    if request.west < request.east
                    else lon >= request.west or lon <= request.east
                )
                if request.south <= lat <= request.north and in_lon:
                    nodes[node] = {"lat": lat, "lon": lon}
        candidates = list(nodes.values())
        random.Random(42).shuffle(candidates)
        candidates = candidates[:100]
        pairs = []
        for i, a in enumerate(candidates):
            for b in candidates[i + 1 :]:
                distance = GEOD.inv(a["lon"], a["lat"], b["lon"], b["lat"])[2]
                if request.min_length_m <= distance <= request.max_length_m:
                    pairs.append((a, b))
        random.Random(17).shuffle(pairs)
        for a, b in pairs[:MAX_CANDIDATES]:
            if job["status"] == "cancelled":
                return
            mission = MissionRequest(
                start=a,
                end=b,
                max_deviation_m=request.max_deviation_m,
                strict=request.strict,
                allow_unverified_crossings=request.allow_unverified_crossings,
            )
            result = await asyncio.to_thread(analyse, mission, data)
            job["evaluated"] += 1
            job["progress"] = round(100 * job["evaluated"] / min(MAX_CANDIDATES, len(pairs)))
            if result["mission"]:
                storage.save_mission(result)
                job["results"].append(result)
                job["results"].sort(
                    key=lambda r: (
                        r["mission"]["corridor_compliant"] is False,
                        r["status"] != "mapped",
                        r["mission"]["max_deviation_m"],
                        len(r["obstacles"]),
                        r["mission"]["distance_m"],
                    )
                )
                job["results"] = job["results"][: request.max_results]
            job["message"] = f"Evaluated {job['evaluated']} candidates using one cached region."
        if job["status"] != "cancelled":
            job.update(
                status="complete",
                progress=100,
                message=f"Evaluated {job['evaluated']} candidates. Found {len(job['results'])} missions. This is a bounded sample, not an exhaustive search.",
            )
    except Exception as error:
        if job["status"] != "cancelled":
            job.update(
                status="failed",
                message=str(error)
                if isinstance(error, ValueError) or type(error).__name__ == "ProviderError"
                else "Discovery could not complete. Try a smaller area.",
            )
