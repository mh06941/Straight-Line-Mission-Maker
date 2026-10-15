import type * as MapLibre from "maplibre-gl";

export type MapLibreRuntime = typeof MapLibre;

declare global {
  interface Window {
    maplibregl?: MapLibreRuntime;
  }
}

let pending: Promise<MapLibreRuntime> | null = null;

/** Load the installed browser bundle as a classic script, its supported UMD
 * entry point. Vite copies this local URL into production assets; the runtime
 * never imports the dependency optimiser's ESM wrapper or assumes its exports.
 */
export function loadMapLibre(): Promise<MapLibreRuntime> {
  if (window.maplibregl?.Map) return Promise.resolve(window.maplibregl);
  if (pending) return pending;

  pending = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = new URL(
      "../../node_modules/maplibre-gl/dist/maplibre-gl.js",
      import.meta.url,
    ).href;
    script.async = true;

    const fail = () => {
      clearTimeout(timeout);
      script.remove();
      pending = null;
      reject(new Error("The map engine could not load."));
    };
    const timeout = window.setTimeout(fail, 15000);
    script.onerror = fail;
    script.onload = () => {
      clearTimeout(timeout);
      if (window.maplibregl?.Map) resolve(window.maplibregl);
      else fail();
    };
    document.head.append(script);
  });

  return pending;
}
