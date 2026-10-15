"""Optional live OSM check. Each region uses one cached bounded query, not synthetic data."""

import argparse
import asyncio
import json

import networkx as nx

from app.analysis import analyse
from app.geo import GEOD, MissionGeometry
from app.models import MissionRequest
from app.providers import ProviderError, provider
from app.routing import build_graph

REGIONS = {
    "london": (51.5074, -0.1278),
    "wales": (52.074, -3.125),
    "alps": (46.0207, 7.7491),
    "adelaide": (-34.9285, 138.6007),
    "canada": (55.0, -110.0),
    "border": (47.585, 7.59),
}


async def check(name):
    lat, lon = REGIONS[name]
    initial = MissionRequest(start={"lat": lat, "lon": lon}, bearing=90, distance_m=500)
    geo = MissionGeometry(initial)
    data = await provider.region(geo.bounds(500))
    graph, _ = await asyncio.to_thread(build_graph, data["elements"], geo, True)
    record = {
        "region": name,
        "real_osm_features": len(data["elements"]),
        "eligible_edges": graph.number_of_edges(),
        "cached": data["cached"],
    }
    if not graph.number_of_edges():
        record.update(
            status="insufficient_data", note="No strict-access evidence; this is not proof of impassability."
        )
        return record
    component = max(nx.connected_components(graph), key=len)
    start = next(iter(component))
    lengths = nx.single_source_dijkstra_path_length(graph, start, cutoff=1200, weight="length")
    for end in sorted(lengths, key=lengths.get, reverse=True):
        a, b = graph.nodes[start]["coord"], graph.nodes[end]["coord"]
        if GEOD.inv(*a, *b)[2] >= 25:
            request = MissionRequest(
                start={"lon": a[0], "lat": a[1]}, end={"lon": b[0], "lat": b[1]}, max_deviation_m=1000
            )
            result = await asyncio.to_thread(analyse, request, data)
            record.update(
                status=result["status"],
                message=result["message"],
                start=request.start.model_dump(),
                end=request.end.model_dump(),
            )
            if result["mission"]:
                record.update(
                    distance_m=round(result["mission"]["distance_m"], 1),
                    max_deviation_m=round(result["mission"]["max_deviation_m"], 1),
                    corridor_compliant=result["mission"]["corridor_compliant"],
                )
                assert result["walking"] and result["mission"]["corridor_compliant"]
            return record
    record.update(status="insufficient_data", note="Eligible component has no 25 m endpoint pair.")
    return record


async def main(names):
    for name in names:
        try:
            print(json.dumps(await check(name)), flush=True)
        except ProviderError as error:
            print(
                json.dumps({"region": name, "status": "provider_unavailable", "error": str(error)}),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region",
        action="append",
        choices=REGIONS,
        help="Repeat to check multiple regions; defaults to London.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.region or ["london"]))
