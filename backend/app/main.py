import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import discovery, storage
from .analysis import analyse
from .geo import MissionGeometry
from .grading import RULES, grade_deviation
from .models import DiscoveryRequest, MissionRequest
from .providers import ProviderError, provider

analysis_slots = asyncio.Semaphore(2)
tasks = set()


@asynccontextmanager
async def lifespan(app):
    yield
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title="StraightLine",
    version="0.1.0",
    lifespan=lifespan,
    description="WGS84 mission planning. Mapped data is evidence, not proof of safe or legal passage.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0", "elevation": "unavailable", "data_source": "OpenStreetMap"}


@app.get("/api/grading")
def grading_scale():
    """Tiered grading of a generated mission's maximum deviation, in metres."""
    return {
        "metric": "max_deviation_m",
        "scope": "planned_mission_route",
        "rules": RULES,
        "note": "Planning estimate from unrounded modelled maximum deviation. A completed mission requires a recorded traveler track.",
    }


@app.get("/api/geocode")
async def geocode(q: str = Query(min_length=2, max_length=200)):
    if len(q.strip()) < 2:
        raise HTTPException(422, "Enter at least two characters.")
    try:
        return await provider.geocode(q.strip())
    except ProviderError as error:
        raise HTTPException(503, str(error)) from error


@app.post("/api/missions/preview")
def preview(request: MissionRequest):
    try:
        return MissionGeometry(request).preview(request.max_deviation_m)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/missions/analyse")
async def analyse_mission(request: MissionRequest):
    try:
        geo = MissionGeometry(request)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if analysis_slots.locked():
        raise HTTPException(429, "Two analyses are already running. Please retry shortly.")
    async with analysis_slots:
        try:
            # A finite 1 km buffer provides walking alternatives without silently increasing the mission corridor.
            data = await provider.region(geo.bounds(max(1000, request.max_deviation_m + 200)))
            result = await asyncio.to_thread(analyse, request, data)
        except ProviderError as error:
            result = await asyncio.to_thread(analyse, request, provider_error=str(error))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    storage.save_mission(result)
    return result


@app.get("/api/missions/{mission_id}")
def get_mission(mission_id: str):
    result = storage.load_mission(mission_id)
    if result is None:
        raise HTTPException(404, "Mission not found. Shared parameters can be used to rebuild it.")
    # Older saved analyses already contain the metric needed by the grading scale.
    result["planned_grade"] = grade_deviation((result.get("mission") or {}).get("max_deviation_m"))
    return result


@app.post("/api/discovery/start", status_code=202)
async def start_discovery(request: DiscoveryRequest):
    try:
        job = discovery.new_job(request)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    task = asyncio.create_task(discovery.run_job(job, request))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return job


@app.get("/api/discovery/{job_id}")
def get_discovery(job_id: str):
    if job_id not in discovery.jobs:
        raise HTTPException(404, "Search not found. Jobs do not survive server restarts.")
    return discovery.jobs[job_id]


@app.post("/api/discovery/{job_id}/cancel")
def cancel_discovery(job_id: str):
    job = get_discovery(job_id)
    if job["status"] in {"running", "queued"}:
        job.update(
            status="cancelled",
            message="Search cancelled. Any current bounded candidate will finish before work stops.",
        )
    return job


@app.get("/api/export/{format}/{mission_id}")
def export_mission(
    format: Literal["gpx", "geojson", "summary"],
    mission_id: str,
    route: Literal["ideal", "walking", "mission"] = "ideal",
):
    mission = get_mission(mission_id)
    geometry = mission["ideal"] if route == "ideal" else (mission.get(route) or {}).get("geometry")
    if not geometry and format != "summary":
        raise HTTPException(
            422, "The selected route is unavailable. Export the ideal line or analyse a route first."
        )
    filename = f"straightline-{mission_id[:8]}-{route}.{format if format != 'summary' else 'json'}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if format == "summary":
        return Response(json.dumps(mission, indent=2), media_type="application/json", headers=headers)
    if format == "geojson":
        return Response(
            json.dumps(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "mission_id": mission_id,
                        "route": route,
                        "source": "OpenStreetMap contributors",
                        "access_note": "Geographic plan only; check local access and conditions.",
                        "planned_grade": mission.get("planned_grade") if route == "mission" else None,
                        "corridor_compliant": (mission.get(route) or {}).get("corridor_compliant"),
                        "target_deviation_m": mission["max_deviation_m"],
                        "verification_sections": (mission.get(route) or {}).get("verification_sections", []),
                    },
                }
            ),
            media_type="application/geo+json",
            headers=headers,
        )
    root = Element("gpx", version="1.1", creator="StraightLine", xmlns="http://www.topografix.com/GPX/1/1")
    if route == "mission":
        for index, check in enumerate(mission["mission"].get("verification_sections", []), start=1):
            lon, lat = check["coordinate"]
            waypoint = SubElement(root, "wpt", lat=str(lat), lon=str((lon + 180) % 360 - 180))
            SubElement(waypoint, "name").text = f"Check {index}: {check['name']}"
            SubElement(waypoint, "desc").text = check["reason"]
            SubElement(waypoint, "type").text = "On-site verification"
    track = SubElement(root, "trk")
    SubElement(track, "name").text = f"StraightLine — {route}"
    description = "Planning data, not verified safe or legal access. © OpenStreetMap contributors."
    if route == "mission" and mission.get("planned_grade"):
        grade = mission["planned_grade"]
        description += (
            f" Planned grade: {grade['label']}; maximum deviation {grade['max_deviation_m']:.2f} m."
            " Grade is an estimate of the planned route, not a completed traveler track."
        )
    if route == "mission":
        selected = mission["mission"]
        description += (
            f" Target corridor: ±{mission['max_deviation_m']:g} m; "
            f"{'within target' if selected.get('corridor_compliant') else 'exceeds target'}. "
            f"{len(selected.get('verification_sections', []))} sections need on-site verification; see the JSON summary for locations."
        )
    SubElement(track, "desc").text = description
    segment = SubElement(track, "trkseg")
    for lon, lat in geometry["coordinates"]:
        SubElement(segment, "trkpt", lat=str(lat), lon=str((lon + 180) % 360 - 180))
    return Response(
        tostring(root, encoding="utf-8", xml_declaration=True),
        media_type="application/gpx+xml",
        headers=headers,
    )


# One-origin deployment: build the frontend, then let FastAPI serve its assets.
dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.is_dir():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Unknown API endpoint.")
        return FileResponse(dist / "index.html")
