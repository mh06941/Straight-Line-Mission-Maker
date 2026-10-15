import { expect, test } from "@playwright/test";

test("map worker processes data in development and production", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const state = window as typeof window & {
      mapWorkerMessages: number;
      mapWorkerErrors: string[];
    };
    state.mapWorkerMessages = 0;
    state.mapWorkerErrors = [];
    const NativeWorker = window.Worker;
    window.Worker = class extends NativeWorker {
      constructor(...args: ConstructorParameters<typeof Worker>) {
        super(...args);
        this.addEventListener("message", () => state.mapWorkerMessages++);
        this.addEventListener("error", (event) =>
          state.mapWorkerErrors.push(event.message),
        );
      }
    };
  });
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  for (const url of ["http://127.0.0.1:8001/", "http://127.0.0.1:5174/"]) {
    await page.goto(url);
    await expect(page.locator(".maplibregl-canvas")).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as typeof window & { mapWorkerMessages: number })
              .mapWorkerMessages,
        ),
      )
      .toBeGreaterThan(0);
    expect(
      await page.evaluate(
        () =>
          (window as typeof window & { mapWorkerErrors: string[] })
            .mapWorkerErrors,
      ),
    ).toEqual([]);
  }
});

test("planner loads even when the optimised MapLibre module has no default export", async ({
  page,
}) => {
  const errors: string[] = [];
  let brokenWrapperRequests = 0;
  page.on("pageerror", (error) => errors.push(error.message));
  // Reproduce the user's broken wrapper contract. The old import prevents
  // React from mounting with this response; the browser-asset loader avoids it.
  await page.route("**/node_modules/.vite/deps/maplibre-gl.js*", (route) => {
    brokenWrapperRequests++;
    return route.fulfill({
      contentType: "text/javascript",
      body: "export const Map = class {};",
    });
  });
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  await page.goto("http://127.0.0.1:5174/");
  await expect(
    page.getByRole("heading", { name: /Every adventure/ }),
  ).toBeVisible();
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Zoom in", exact: true }),
  ).toBeVisible();
  expect(brokenWrapperRequests).toBe(0);
  expect(errors).toEqual([]);
});

test("failed map-module download leaves the planner and help usable", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route(
    "**/node_modules/maplibre-gl/dist/maplibre-gl.mjs*",
    (route) => route.abort(),
  );
  await page.goto("http://127.0.0.1:5174/");
  await expect(
    page.getByRole("heading", { name: /Every adventure/ }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "map engine could not load",
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Plan a mission" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Start point coordinates" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "How it works" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(errors).toEqual([]);
});

// Exercise Vite's development dependency optimiser as well as the production
// bundle. A module-export mismatch can blank the app before React mounts.
test("development planner renders with cold and warm dependencies", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  await page.goto("http://127.0.0.1:5174/");

  for (let visit = 0; visit < 2; visit++) {
    await expect(
      page.getByRole("heading", { name: /Every adventure/ }),
    ).toBeVisible();
    // Rendering the sidebar alone is insufficient: the map constructor and
    // controls must be available through the imported module as well.
    await expect(page.locator(".maplibregl-canvas")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Zoom in", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Map layers", exact: true }).click();
    await expect(
      page.getByRole("checkbox", { name: "Buildings", exact: true }),
    ).toBeChecked();
    await page.getByRole("button", { name: "Close map layers" }).click();
    if (visit === 0) await page.reload();
  }

  expect(errors).toEqual([]);
});

test("development planner remains usable without WebGL", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      type: string,
      ...args: unknown[]
    ) {
      if (["webgl", "webgl2", "experimental-webgl"].includes(type)) return null;
      return original.apply(this, [type, ...args] as Parameters<
        typeof original
      >);
    } as typeof original;
  });
  await page.goto("http://127.0.0.1:5174/");
  await expect(
    page.getByRole("heading", { name: /Every adventure/ }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "could not initialize WebGL",
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Plan a mission" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Start point coordinates" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "How it works" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(errors).toEqual([]);
});
