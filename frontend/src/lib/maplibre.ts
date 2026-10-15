import type * as MapLibre from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

export type MapLibreRuntime = typeof MapLibre;

let pending: Promise<MapLibreRuntime> | null = null;

/** MapLibre 6 exposes native named ESM exports. Import the namespace lazily so
 * a failed download leaves the planner usable, without assuming a default
 * export. Vite bundles the separate module worker and its imports as well.
 */
export function loadMapLibre(): Promise<MapLibreRuntime> {
  if (!pending) {
    pending = import("maplibre-gl")
      .then((library) => {
        library.setWorkerUrl(workerUrl);
        return library;
      })
      .catch((error) => {
        pending = null;
        throw error;
      });
  }
  return pending;
}
