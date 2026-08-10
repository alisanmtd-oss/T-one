const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { _electron: electron } = require(process.env.TONE_PLAYWRIGHT_PACKAGE || "playwright");

const root = path.resolve(__dirname, "..");
const electronPath = process.env.TONE_PUBLIC_ELECTRON || path.join(root, "desktop_public", "node_modules", "electron", "dist", "electron.exe");
const outputDir = path.join(root, "output", "playwright");
const resultPath = path.join(outputDir, "community_workspace_acceptance_latest.json");
const screenshotPath = path.join(root, "assets", "screenshots", "t-one-community-workspace-zh.png");
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "tone-community-workspace-"));
const profile = path.join(tempRoot, "profile");
fs.mkdirSync(outputDir, { recursive: true });

const evidence = { ok: false, console_errors: [], page_errors: [], external_requests: [], external_actions: 0 };

async function launch() {
  const packaged = path.basename(electronPath).toLowerCase() !== "electron.exe";
  const args = packaged
    ? [`--user-data-dir=${profile}`]
    : [path.join(root, "desktop_public"), `--user-data-dir=${profile}`];
  const desktop = await electron.launch({ executablePath: electronPath, args, cwd: root });
  const page = await desktop.firstWindow();
  page.on("console", (message) => { if (message.type() === "error") evidence.console_errors.push(message.text()); });
  page.on("pageerror", (error) => evidence.page_errors.push(String(error.message || error)));
  page.on("request", (request) => { if (!request.url().startsWith("file:")) evidence.external_requests.push(request.url()); });
  await page.setViewportSize({ width: 1100, height: 720 });
  return { desktop, page };
}

async function main() {
  assert.equal(fs.existsSync(electronPath), true, `Electron executable not found: ${electronPath}`);
  let session = await launch();
  try {
    const { page } = session;
    await page.locator("#homeView").waitFor({ state: "visible" });
    await page.locator("#heroNewProject").click();
    await page.locator('#projectForm input[name="name"]').fill("社区版真实项目");
    await page.locator('#projectForm textarea[name="description"]').fill("验证项目、任务、历史和能力分配");
    await page.locator('#projectForm button[value="default"]').click();
    try {
      await page.locator("#taskDialog").waitFor({ state: "visible", timeout: 5000 });
    } catch (error) {
      const diagnostics = await page.evaluate(() => ({
        toast: document.querySelector("#toast")?.textContent,
        projectTree: document.querySelector("#projectTree")?.textContent,
        projectDialogOpen: document.querySelector("#projectDialog")?.open,
      }));
      throw new Error(`Project creation did not open task dialog: ${JSON.stringify(diagnostics)}; ${error.message}`);
    }
    await page.locator('#taskForm input[name="name"]').fill("第一项运营任务");
    await page.locator('#taskForm button[value="default"]').click();
    await page.locator("#taskView").waitFor({ state: "visible" });
    await page.locator("#prompt").fill("记住这条任务上下文，重开后继续。");
    await page.locator('#composer button[type="submit"]').click();
    assert.equal(await page.locator("#messages .message").count(), 2);

    await page.locator('[data-view="market"]').first().click();
    await page.locator('[data-kind="skill"]').click();
    await page.locator('[data-capability="shein-skill"]').click();
    assert.equal(await page.locator('[data-capability="shein-skill"]').innerText(), "已加入当前任务");

    await page.locator('[data-view="connections"]').first().click();
    await page.locator("#addConnection").click();
    await page.locator('#connectionForm select[name="type"]').selectOption("cli");
    await page.locator('#connectionForm input[name="name"]').fill("Node CLI");
    await page.locator('#connectionForm input[name="target"]').fill("node.exe");
    await page.locator('#connectionForm input[name="arguments"]').fill('["-e","process.stdout.write(\'CLI_OK\')"]');
    await page.locator('#connectionForm button[value="default"]').click();
    assert.match(await page.locator("#cliConnections").innerText(), /已保存，未连接/);
    await page.locator("[data-detect]").click();
    await page.locator("#cliConnections .pill").filter({ hasText: "已检测" }).waitFor();

    await page.locator("[data-task]").click();
    await page.locator("#taskExecutor").selectOption({ label: "Node CLI" });
    await page.locator("#prompt").fill("执行一次本地 CLI 回传测试");
    await page.locator("#runCli").click();
    await page.locator("#messages .message").filter({ hasText: "CLI_OK" }).waitFor();

    await page.screenshot({ path: screenshotPath, fullPage: false });
    const dimensions = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth }));
    assert.ok(dimensions.width <= dimensions.viewport, JSON.stringify(dimensions));
  } finally {
    await session.desktop.close().catch(() => {});
  }

  session = await launch();
  try {
    const { page } = session;
    await page.locator('[data-task]').click();
    await page.locator("#taskView").waitFor({ state: "visible" });
    assert.equal(await page.locator("#taskName").innerText(), "第一项运营任务");
    assert.match(await page.locator("#messages").innerText(), /记住这条任务上下文/);
    assert.match(await page.locator("#capabilitySummary").innerText(), /SHEIN 运营 Skill/);
    await page.locator('[data-view="connections"]').first().click();
    assert.match(await page.locator("#cliConnections").innerText(), /已检测/);
    const workspacePath = await page.locator("#workspacePath").innerText().catch(() => "");
    evidence.workspace_path = workspacePath;
  } finally {
    await session.desktop.close().catch(() => {});
  }

  assert.deepEqual(evidence.console_errors, []);
  assert.deepEqual(evidence.page_errors, []);
  assert.deepEqual(evidence.external_requests, []);
  evidence.ok = true;
  evidence.viewport = "1100x720";
  evidence.runtime = path.basename(electronPath);
  evidence.verified = ["create_project", "create_task", "save_history", "assign_skill", "register_cli", "detect_cli", "run_cli_real_result", "restart_restore"];
  evidence.screenshot = path.relative(root, screenshotPath).replaceAll("\\", "/");
}

main().catch((error) => {
  evidence.error = String(error.stack || error.message || error);
  process.exitCode = 1;
}).finally(() => {
  fs.writeFileSync(resultPath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  fs.rmSync(tempRoot, { recursive: true, force: true });
  process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`);
});
