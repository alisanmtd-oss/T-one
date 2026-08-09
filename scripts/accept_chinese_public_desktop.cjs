const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { _electron: electron } = require(process.env.TONE_PLAYWRIGHT_PACKAGE || "playwright");

const root = path.resolve(__dirname, "..");
const electronPath = process.env.TONE_PUBLIC_ELECTRON || path.join(
  root, "desktop_public", "node_modules", "electron", "dist", "electron.exe",
);
const outputDir = path.join(root, "output", "playwright");
const resultPath = path.join(outputDir, "chinese_public_desktop_latest.json");
const screenshotPath = path.join(root, "assets", "screenshots", "t-one-capability-market-zh.png");
fs.mkdirSync(outputDir, { recursive: true });
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "tone-public-zh-"));

async function main() {
  assert.equal(fs.existsSync(electronPath), true, `Electron executable not found: ${electronPath}`);
  const evidence = { ok: false, console_errors: [], page_errors: [], external_requests: [] };
  const app = await electron.launch({
    executablePath: electronPath,
    args: [path.join(root, "desktop_public"), `--user-data-dir=${path.join(tempRoot, "profile")}`],
    cwd: root,
  });
  try {
    const page = await app.firstWindow();
    page.on("console", (message) => {
      if (message.type() === "error") evidence.console_errors.push(message.text());
    });
    page.on("pageerror", (error) => evidence.page_errors.push(String(error.message || error)));
    page.on("request", (request) => {
      if (!request.url().startsWith("file:")) evidence.external_requests.push(request.url());
    });
    await page.setViewportSize({ width: 1100, height: 720 });
    await page.locator("#capabilityMarket").click();
    await page.locator("#marketView").waitFor({ state: "visible" });
    assert.equal(await page.locator('[data-capability-type="agent"]').count(), 1);
    assert.equal(await page.locator('[data-capability-type="skill"]').count(), 1);
    assert.equal(await page.locator('[data-capability-type="mcp"]').count(), 1);
    assert.equal(await page.locator('[data-capability-type="cli"]').count(), 1);
    assert.equal(await page.locator('.capability-card[data-kind="skill"]:visible').count(), 4);
    const sheinButton = page.locator('[data-assign-capability="shein-skill"]');
    await sheinButton.click();
    assert.equal(await sheinButton.innerText(), "已加入示例任务");
    assert.match(await page.locator("#marketStatus").innerText(), /仅保存在这台电脑的演示数据中/);
    await page.locator('[data-capability-type="mcp"]').click();
    assert.match(await page.locator('.capability-card[data-kind="mcp"]').innerText(), /未配置/);
    await page.locator('[data-capability-type="cli"]').click();
    assert.equal(await page.locator('.capability-card[data-kind="cli"]:visible').count(), 2);
    assert.match(await page.locator('.capability-card[data-kind="cli"]').first().innerText(), /未检测/);
    const dimensions = await page.evaluate(() => ({
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
    }));
    assert.ok(dimensions.documentWidth <= dimensions.viewportWidth, JSON.stringify(dimensions));
    await page.screenshot({ path: screenshotPath, fullPage: false });
    assert.deepEqual(evidence.console_errors, []);
    assert.deepEqual(evidence.page_errors, []);
    assert.deepEqual(evidence.external_requests, []);
    evidence.ok = true;
    evidence.viewport = "1100x720";
    evidence.visible_counts = { skill: 4, mcp: 1, cli: 2 };
    evidence.local_assignment = "shein-skill";
    evidence.screenshot = path.relative(root, screenshotPath).replaceAll("\\", "/");
  } finally {
    await app.close().catch(() => {});
    fs.writeFileSync(resultPath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  }
  process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || error}\n`);
  process.exitCode = 1;
});
