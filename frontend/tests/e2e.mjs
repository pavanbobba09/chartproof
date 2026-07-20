import assert from "node:assert/strict";
import { accessSync, constants } from "node:fs";
import process from "node:process";
import { chromium } from "playwright-core";

const baseUrl = process.env.E2E_BASE_URL || "http://localhost:3000";

function chromeExecutable() {
  const candidates = [
    process.env.CHROME_PATH,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      accessSync(candidate, constants.X_OK);
      return candidate;
    } catch {
      // Try the next standard Chrome location.
    }
  }
  throw new Error(
    "Chrome was not found. Set CHROME_PATH to a Chrome or Chromium executable."
  );
}

const browser = await chromium.launch({
  executablePath: chromeExecutable(),
  headless: true,
  args: ["--no-sandbox"],
});

const page = await browser.newPage();
const browserErrors = [];
page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
page.on("console", (message) => {
  if (message.type() === "error") {
    const location = message.location();
    browserErrors.push(
      `console ${location.url || "unknown"}:${location.lineNumber}: ${message.text()}`
    );
  }
});
page.on("response", (response) => {
  if (response.status() >= 400) {
    browserErrors.push(`http ${response.status()}: ${response.url()}`);
  }
});

try {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Case bank" }).waitFor();
  assert.equal(await page.getByTestId("case-count").textContent(), "100");
  assert.equal(await page.getByTestId("case-row").count(), 20);

  await page.getByRole("button", { name: "Next" }).click();
  await page.getByText("Page 2 of 5").waitFor();
  await page.getByText("sepsis_021", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Previous" }).click();

  const datasetPurpose = page.getByLabel("Dataset purpose");
  await datasetPurpose.selectOption("volume_test");
  await page.getByText("Showing 20 of 85 matching records").waitFor();
  await datasetPurpose.selectOption("all");

  const search = page.getByRole("searchbox", { name: "Search" });
  await search.fill("sepsis_001");
  assert.equal(await page.getByTestId("case-row").count(), 1);

  await page.getByRole("link", { name: "Audit sepsis_001" }).click();
  await page.waitForURL("**/audit/sepsis_001");
  await page.getByRole("heading", { name: "Audit · sepsis_001" }).waitFor();
  await page.getByRole("heading", { name: "Evidence table" }).waitFor();
  const evidenceJump = page.getByRole("button", { name: /^Show E1 in chart/ });
  await evidenceJump.click();
  const highlighted = page.locator(".line-highlight");
  await highlighted.first().waitFor();
  assert.ok((await highlighted.count()) >= 1);

  await page.getByRole("link", { name: "← Cases" }).click();
  await page.waitForURL(baseUrl + "/");
  await page.getByRole("searchbox", { name: "Search" }).fill("sepsis_001");
  await page.getByRole("link", { name: "Train with sepsis_001" }).click();
  await page.waitForURL("**/training/sepsis_001");
  await page.getByRole("heading", { name: "Training · sepsis_001" }).waitFor();

  await page.getByRole("button", { name: "supported", exact: true }).click();
  const lineSelection = page.locator("#line-hp-5 button");
  assert.equal(await lineSelection.getAttribute("aria-label"), "Select hp line 5");
  await lineSelection.focus();
  await page.keyboard.press("Enter");
  assert.equal(await lineSelection.getAttribute("aria-pressed"), "true");
  await page.getByRole("button", { name: "Submit" }).click();
  await page.getByRole("heading", { name: /Verdict correct/ }).waitFor();
  await page.getByText(/Evidence score:/).waitFor();

  assert.deepEqual(browserErrors, [], browserErrors.join("\n"));
  console.log("E2E passed: case bank -> audit evidence -> training grade");
} finally {
  await browser.close();
}
