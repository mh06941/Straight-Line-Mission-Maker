import type { Preview } from "../types";

export function downloadPreview(
  preview: Preview,
  format: "gpx" | "geojson" | "summary",
) {
  let content: string, type: string;
  if (format === "gpx") {
    content = `<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="StraightLine" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>StraightLine ideal geodesic</name><desc>Ideal geometry only. Access and obstacles are not assessed.</desc><trkseg>${preview.ideal.coordinates.map(([lon, lat]) => `<trkpt lat="${lat}" lon="${((((lon + 180) % 360) + 360) % 360) - 180}"/>`).join("")}</trkseg></trk></gpx>`;
    type = "application/gpx+xml";
  } else {
    content = JSON.stringify(
      format === "geojson"
        ? {
            type: "Feature",
            geometry: preview.ideal,
            properties: {
              route: "ideal",
              note: "Access and obstacles are not assessed.",
            },
          }
        : {
            ...preview,
            note: "Ideal geometry only; no OSM analysis performed.",
          },
      null,
      2,
    );
    type = format === "geojson" ? "application/geo+json" : "application/json";
  }
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `straightline-ideal.${format === "summary" ? "json" : format}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
