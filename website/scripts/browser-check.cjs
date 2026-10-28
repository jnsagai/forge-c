// Optional QA: use an external Playwright installation and Chromium executable.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

(async () => {
  const origin = process.argv[2];
  const output = process.argv[3];
  if (!origin?.endsWith("/") || !output)
    throw new Error(
      "Provide site URL with trailing slash and screenshot directory.",
    );
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_EXECUTABLE
      ? { executablePath: process.env.BROWSER_EXECUTABLE }
      : {}),
  });
  const errors = [];
  const checks = [];
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("response", (response) => {
      if (response.status() >= 400)
        errors.push(`${response.status()} ${response.url()}`);
    });
    const visit = async (route) => {
      const response = await page.goto(new URL(route, origin).href, {
        waitUntil: "networkidle",
      });
      assert.equal(response.status(), 200);
    };
    const noOverflow = async () =>
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
        `Overflow at ${await page.evaluate(() => innerWidth)}: ${page.url()}`,
      );
    await visit("");
    await page.keyboard.press("Tab");
    assert.equal(await page.locator(":focus").textContent(), "Skip to content");
    for (const title of ["Implementation", "Qualification", "Requirements"]) {
      await page
        .getByRole("button", { name: new RegExp(`SWE\\.\\d ${title}`) })
        .click();
      assert.equal(await page.locator("#stage-title").textContent(), title);
    }
    await page.getByRole("button", { name: "Blocked", exact: true }).click();
    assert.equal(
      await page.locator("#package-status").textContent(),
      "BLOCKED",
    );
    await page
      .getByRole("button", { name: "Review-ready", exact: true })
      .click();
    assert.equal(
      await page.locator("#package-status").textContent(),
      "READY_FOR_OFFLINE_REVIEW",
    );
    await page.screenshot({
      path: path.join(output, "home-desktop.png"),
      fullPage: true,
    });
    checks.push(
      "Desktop home, keyboard skip link, six-phase controls, package-state controls",
    );
    const slider = page.getByRole("slider", {
      name: "Recorded workflow event",
    });
    await page
      .getByRole("button", { name: "Next event", exact: false })
      .click();
    assert.equal(
      await page.locator("[data-replay-outcome]").textContent(),
      "REWORK",
    );
    await page
      .getByRole("button", { name: "Play recorded workflow replay" })
      .click();
    await page
      .getByRole("button", { name: "Pause recorded workflow replay" })
      .click();
    assert.equal(
      await page
        .locator("[data-replay]")
        .evaluate((el) => el.classList.contains("playing")),
      false,
    );
    await slider.focus();
    await slider.press("End");
    assert.equal(
      await page.locator("[data-replay-outcome]").textContent(),
      "READY_FOR_OFFLINE_REVIEW",
    );
    assert.equal(await page.locator(".replay-station.passed").count(), 6);
    await page.screenshot({
      path: path.join(output, "recorded-replay.png"),
      fullPage: false,
    });
    await page.locator(".replay-video summary").click();
    const video = page.locator("video");
    await video.evaluate(async (video) => {
      video.load();
      await new Promise((resolve, reject) => {
        video.onloadedmetadata = resolve;
        video.onerror = reject;
      });
    });
    assert.ok(
      Math.abs((await video.evaluate((video) => video.duration)) - 45) < 0.2,
    );
    await video.evaluate(async (video) => {
      await video.play();
    });
    await page.waitForTimeout(500);
    assert.ok(await video.evaluate((video) => video.currentTime > 0));
    await video.evaluate((video) => {
      video.pause();
      video.currentTime = 20;
    });
    assert.equal(await video.locator("track").getAttribute("kind"), "captions");
    await page.locator(".replay-video summary").click();
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page
      .getByRole("button", { name: "Play recorded workflow replay" })
      .click();
    const animationName = await page
      .locator(".replay-station.active")
      .evaluate((el) => getComputedStyle(el, "::before").animationName);
    assert.equal(animationName, "none");
    await page
      .getByRole("button", { name: "Pause recorded workflow replay" })
      .click();
    await page.emulateMedia({ reducedMotion: "no-preference" });
    checks.push(
      "Recorded replay stepping, play/pause, final gates, reduced motion, 45-second video playback and captions",
    );

    await page.keyboard.press("Control+k");
    const input = page.locator("#pagefind-search input");
    await input.waitFor();
    for (const [query, route] of [
      ["verify_archive", "reference/generated/python/"],
      ["provided-from", "reference/generated/commands/"],
      ["IWDG", "status/"],
    ]) {
      await input.fill(query);
      await page.waitForFunction(
        (route) =>
          [...document.querySelectorAll("#pagefind-search a")].some((link) =>
            link.href.includes(route),
          ),
        route,
      );
      const links = await page
        .locator("#pagefind-search a")
        .evaluateAll((nodes) => nodes.map((node) => node.href));
      assert.ok(
        links.every((link) => link.startsWith(origin)),
        `Search base escaped for ${query}`,
      );
    }
    await page.screenshot({ path: path.join(output, "search.png") });
    await page.keyboard.press("Escape");
    assert.equal(
      await page.locator("#forge-search").evaluate((dialog) => dialog.open),
      false,
    );
    checks.push(
      "Keyboard search, Python/CLI/status search results, project prefix, Escape",
    );

    await visit("docs/getting-started/first-work-order/");
    await page
      .locator("starlight-theme-select select")
      .first()
      .selectOption("dark");
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await page.screenshot({ path: path.join(output, "docs-desktop.png") });
    await page
      .locator("starlight-theme-select select")
      .first()
      .selectOption("light");
    assert.equal(
      await page.locator("html").getAttribute("data-theme"),
      "light",
    );
    await page.screenshot({ path: path.join(output, "docs-light.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await noOverflow();
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    await page
      .locator("#starlight__sidebar")
      .getByRole("link", { name: "Overview", exact: true })
      .click();
    assert.ok(page.url().endsWith("/docs/"));
    await page.screenshot({ path: path.join(output, "docs-mobile.png") });
    checks.push(
      "Documentation desktop and mobile, theme selection, mobile menu navigation",
    );

    for (const width of [320, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await visit("");
      await noOverflow();
      if (width === 390)
        await page.screenshot({
          path: path.join(output, "home-mobile.png"),
          fullPage: true,
        });
      await visit("docs/reference/generated/commands/");
      await noOverflow();
    }
    checks.push(
      "Home and reference overflow checks at 320, 390, 768, 1024, 1440 pixels",
    );
    assert.deepEqual(errors, []);
    const report = { origin, result: "PASS", checks, errors };
    await fs.writeFile(
      path.join(output, "browser-report.json"),
      JSON.stringify(report, null, 2) + "\n",
    );
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
