// app.spec.ts — Real media playback, persistent projects, downloads, and responsive layout.
import { test, expect } from "@playwright/test";
import path from "node:path";
test("full local demo playback, library, export, and responsive workflow", async ({
  page,
  request,
}) => {
  // Observe uncaught browser failures while exercising the real API and media.
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    // Include browser console failures, not only uncaught JavaScript exceptions.
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /More Voices/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await expect(
    page.getByText(
      "Scripted sample text and local synthetic voices; this demo does not use live AI.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("こんにちは。今日はいい天気ですね。").last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect
    .poll(() =>
      page.locator("video").evaluate((el: HTMLVideoElement) => el.paused),
    )
    .toBe(false);
  await expect(page.getByText("Translated voice · video paused")).toBeVisible({
    timeout: 15000,
  });
  expect(
    await page.locator("video").evaluate((el: HTMLVideoElement) => el.paused),
  ).toBe(true);
  expect(
    await page.locator("audio").evaluate((el: HTMLAudioElement) => el.paused),
  ).toBe(false);
  await expect
    .poll(
      () => page.locator("video").evaluate((el: HTMLVideoElement) => el.paused),
      { timeout: 10000 },
    )
    .toBe(false);
  await page.getByRole("radio", { name: /Translation Only/ }).check();
  await expect(page.getByText("Translated voice · video paused")).toBeVisible();
  await page.getByRole("radio", { name: /Original Only/ }).check();
  await expect
    .poll(() =>
      page.locator("audio").evaluate((el: HTMLAudioElement) => el.paused),
    )
    .toBe(true);
  await expect
    .poll(() =>
      page.locator("video").evaluate((el: HTMLVideoElement) => el.paused),
    )
    .toBe(false);
  await page.getByRole("button", { name: "Audio only", exact: true }).click();
  await expect(page.locator(".audio-art")).toBeVisible();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await page
    .getByRole("button", { name: "Play sentence 3", exact: true })
    .click();
  await expect(page.locator(".transcript-row.active")).toContainText(
    "私たちはいつもここで話をします。",
  );
  await page
    .getByRole("button", { name: "Favorite sentence 3", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Favorite sentence 3", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: /Translated subtitles/ }).click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/\.srt$/);
  const id = await page.evaluate(() =>
    localStorage.getItem("linguaecho-project"),
  );
  await page
    .getByRole("button", { name: "My Library", exact: true })
    .first()
    .click();
  await expect(page.locator(".library-card").first()).toBeVisible();
  await page.reload();
  await expect(page.getByText("OFFLINE DEMO", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.screenshot({ path: "test-results/desktop.png", fullPage: true });
  expect(errors).toEqual([]);
  // Remove only the fixture project created by this test.
  await request.delete(`/api/projects/${id}`);
});

test("uploads actual video, previews it, and persists metadata without API charges", async ({
  page,
  request,
}) => {
  const health = await (await request.get("/api/health")).json();
  await page.goto("/");
  await page
    .getByLabel("Upload media file")
    .setInputFiles(path.resolve("../fixtures/demo.mp4"));
  await expect(
    page.getByText("Choose languages and start processing"),
  ).toBeVisible();
  await page.getByLabel("Target language", { exact: true }).selectOption("ar");
  if (!health.ai_configured) {
    await page.getByRole("button", { name: "Translate my media" }).click();
    await expect(page.getByRole("alert")).toContainText("OPENAI_API_KEY");
  }
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect
    .poll(() =>
      page.locator("video").evaluate((el: HTMLVideoElement) => el.paused),
    )
    .toBe(false);
  const id = await page.evaluate(() =>
    localStorage.getItem("linguaecho-project"),
  );
  expect((await request.get(`/api/projects/${id}`)).ok()).toBe(true);
  await request.delete(`/api/projects/${id}`);
});
