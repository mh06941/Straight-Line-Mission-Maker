import { expect, test } from "@playwright/test";

test("open plaza route returns to the line around a fountain", async ({
  page,
}) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  const parameters = {
    start: { lat: 51.54, lon: -0.1 },
    bearing: 90,
    distance_m: 1000,
    max_deviation_m: 25,
    strict: false,
    allow_unverified_crossings: false,
  };
  await page.goto(
    `/?mission=${encodeURIComponent(JSON.stringify(parameters))}`,
  );
  const completed = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/missions/analyse") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Analyse mission" }).click();
  const result = await (await completed).json();
  expect(result.mission.max_deviation_m).toBeLessThan(25);
  expect(result.mission.within_percent["10"]).toBeGreaterThan(85);
  await expect(
    page.getByText("A route with unknowns", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Planned mission grade" })
      .locator(".grade-badge"),
  ).toHaveText("Platinum");
  await page.locator(".verification-list summary").click();
  await page.getByRole("button", { name: /Browser test plaza/ }).click();
  await expect(page.locator(".map-legend")).toContainText("To verify");
});

test("relaxed planning locates crossing checks and can disable proposals", async ({
  page,
}) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  const parameters = {
    start: { lat: 51.52, lon: -0.1 },
    bearing: 90,
    distance_m: 1000,
    max_deviation_m: 10,
    strict: false,
    allow_unverified_crossings: true,
  };
  await page.goto(
    `/?mission=${encodeURIComponent(JSON.stringify(parameters))}`,
  );
  const proposals = page.getByRole("checkbox", {
    name: /Propose road crossings to verify/,
  });
  await expect(proposals).toBeChecked();
  await page.getByRole("button", { name: "Analyse mission" }).click();
  await expect(
    page.getByText("Best available mission route", { exact: true }),
  ).toBeVisible();
  await page.locator(".verification-list summary").click();
  await page.getByRole("button", { name: /Cross Browser test road/ }).click();
  await expect(page.locator(".map-legend")).toContainText("To verify");
  await expect(page.locator(".verification-list")).toContainText(
    "check the crossing point, median and barriers on site",
  );
  await page.getByLabel("Export route").selectOption("mission");
  await expect(
    page.getByRole("button", { name: "Download mission" }),
  ).toBeEnabled();
  await proposals.uncheck();
  await page.getByRole("button", { name: "Analyse mission" }).click();
  await expect(
    page.getByText("No connected route found", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Planned mission grade" }),
  ).toHaveCount(0);
  await proposals.check();
  await page.getByRole("button", { name: "Analyse mission" }).click();
  await expect(
    page.getByText("Best available mission route", { exact: true }),
  ).toBeVisible();
  await page.getByRole("region", { name: "Planned mission grade" }).screenshot({
    path: `test-results/best-effort-grade-${test.info().project.name}.png`,
  });
});

test("bounded discovery selects a real analysed candidate", async ({
  page,
}) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  const parameters = {
    start: { lat: 51.5, lon: -0.1 },
    bearing: 90,
    distance_m: 1000,
    max_deviation_m: 50,
    strict: true,
  };
  await page.goto(
    `/?mission=${encodeURIComponent(JSON.stringify(parameters))}`,
  );
  await expect(
    page.getByText("1.00 km", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Discover", exact: true })
    .click();
  await page.getByRole("button", { name: /Draw your search area/ }).click();
  const canvas = page.locator(".maplibregl-canvas");
  const box = (await canvas.boundingBox())!;
  // Keep both clicks clear of search, controls and the instruction overlay.
  await canvas.click({
    position: { x: box.width * 0.03, y: box.height * 0.37 },
  });
  await canvas.click({
    position: { x: box.width * 0.88, y: box.height * 0.7 },
  });
  await page
    .getByRole("spinbutton", { name: "Minimum discovery length in kilometres" })
    .fill("0.1");
  await page
    .getByRole("spinbutton", { name: "Maximum discovery length in kilometres" })
    .fill("2");
  await page.getByRole("button", { name: "Find promising missions" }).click();
  await expect(
    page.getByText("Search complete", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".discovery-card .grade-badge").first(),
  ).toBeVisible();
  await page.locator(".discovery-card").first().click();
  await expect(
    page.getByRole("region", { name: "Mission analysis" }),
  ).toBeVisible();
});

test("plan, analyse, show best effort beyond target, save, share and export", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  // Offline tests intentionally block third-party tiles; geometry and all API operations remain real.
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Every adventure/ }),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Plan a mission" })
    .click();
  await page.getByRole("tab", { name: "Bearing & distance" }).click();
  const start = page.getByRole("textbox", { name: "Start point coordinates" });
  await start.fill("51.5, -0.1");
  await start.press("Tab");
  await page
    .getByRole("spinbutton", { name: "Mission distance", exact: true })
    .fill("1");
  await expect(
    page.getByText("1.00 km", { exact: true }).first(),
  ).toBeVisible();
  const grade = page.getByRole("region", { name: "Planned mission grade" });
  await expect(grade).toHaveCount(0);
  await page.getByRole("button", { name: "Analyse mission" }).click();
  await expect(page.getByText("A line worth exploring")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Mission analysis" }),
  ).toContainText("35 m");
  await expect(grade.locator(".grade-badge")).toHaveText("Gold");
  await expect(grade).toContainText("35.05 m");
  await grade.getByText("View grading thresholds").click();
  await expect(
    grade.getByRole("region", { name: "Planned grading thresholds" }),
  ).toContainText("75 to 100 m inclusive");
  await expect(grade.locator("dt")).toHaveCount(6);
  await page.getByRole("button", { name: /Units: metric/ }).click();
  await expect(grade.locator(".grade-badge")).toHaveText("Gold");
  await page.getByRole("button", { name: /Units: imperial/ }).click();
  await page.getByRole("button", { name: "Save mission", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Mission name" })
    .fill("My first line");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save mission" })
    .click();
  await page.getByRole("button", { name: "Share", exact: true }).click();
  const link = await page
    .getByRole("textbox", { name: "Shareable mission URL" })
    .inputValue();
  expect(new URL(link).searchParams.get("mission")).toContain("51.5");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.getByLabel("Export route").selectOption("mission");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download mission" }).click();
  expect((await download).suggestedFilename()).toMatch(/mission.gpx/);
  await page.getByRole("button", { name: "10 m", exact: true }).click();
  await page.getByRole("button", { name: "Analyse mission" }).click();
  await expect(
    page.getByText("Best available mission route", { exact: true }),
  ).toBeVisible();
  await expect(grade.locator(".grade-badge")).toHaveText("Gold");
  await expect(
    page.getByText("25 m over target", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: /Saved/ })
    .click();
  await page
    .getByRole("button", { name: /My first line/ })
    .first()
    .click();
  await expect(
    page.getByText("1.00 km", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/planner-${test.info().project.name}.png`,
    fullPage: true,
  });
  expect(pageErrors).toEqual([]);
});

test("worldwide search, map picks, layers and help remain usable", async ({
  page,
}) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  await page.goto("/");
  await page
    .getByRole("textbox", {
      name: "Search worldwide or enter latitude, longitude",
    })
    .fill("London");
  await page
    .getByRole("button", { name: "Search location", exact: true })
    .click();
  await page
    .getByRole("button", { name: /London \(offline browser fixture\)/ })
    .click();
  await page.getByRole("button", { name: "Map layers" }).click();
  await page.getByLabel("Buildings", { exact: true }).uncheck();
  await page.getByRole("button", { name: "Close map layers" }).click();
  await page
    .getByRole("button", { name: "Start exploring", exact: true })
    .click();
  const canvas = page.locator(".maplibregl-canvas");
  await expect(canvas).toBeVisible();
  const box = (await canvas.boundingBox())!;
  await canvas.click({
    position: { x: box.width * 0.4, y: box.height * 0.65 },
  });
  await canvas.click({
    position: { x: box.width * 0.7, y: box.height * 0.65 },
  });
  await expect(
    page.getByRole("textbox", { name: "Start point coordinates" }),
  ).not.toHaveValue("");
  await expect(
    page.getByRole("textbox", { name: "Finish point coordinates" }),
  ).not.toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Drag start point" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "How it works" }).click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("region", { name: "Planned grading thresholds" }),
  ).toContainText("Under 10 m");
  await expect(page.getByRole("dialog")).toContainText(
    "green route minimises its greatest deviation",
  );
});
