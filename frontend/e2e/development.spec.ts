import { expect, test } from "@playwright/test";

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
