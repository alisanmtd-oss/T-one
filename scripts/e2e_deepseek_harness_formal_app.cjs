const assert = require("node:assert/strict");
const fs = require("node:fs");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { _electron: electron } = require(process.env.TONE_PLAYWRIGHT_PACKAGE || "playwright");

const executablePath = process.env.TONE_PUBLIC_EXECUTABLE;
assert.ok(executablePath && fs.existsSync(executablePath), "TONE_PUBLIC_EXECUTABLE is required");
const artifactRoot = process.env.TONE_PUBLIC_ARTIFACT_ROOT || path.join(os.tmpdir(), "tone-harness-formal");
const profileRoot = fs.mkdtempSync(path.join(os.tmpdir(), "tone-harness-profile-"));
const profilePath = path.join(profileRoot, "profile");
const workspace = path.join(profilePath, "workspace");
const screenshotPath = path.join(artifactRoot, "deepseek-harness-formal.png");
const resultPath = path.join(artifactRoot, "deepseek-harness-formal.json");

function portIsOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    const done = (value) => { socket.destroy(); resolve(value); };
    socket.setTimeout(250);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
  });
}

async function waitForPortClosed(port) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline && await portIsOpen(port)) {
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  return !(await portIsOpen(port));
}

async function main() {
  fs.mkdirSync(artifactRoot, { recursive: true });
  const result = {
    ok: false,
    version: "0.5.9",
    console_errors: [],
    page_errors: [],
    external_requests: [],
    external_store_actions: 0,
  };
  const launchEnv = { ...process.env, TONE_E2E_ALLOW_PARALLEL: "1" };
  delete launchEnv.TEELAB_AGENT_ROOT;
  delete launchEnv.TEELAB_AGENT_PYTHON;
  delete launchEnv.PYTHONPATH;
  let app;
  let harnessPort = 0;
  try {
    app = await electron.launch({
      executablePath,
      args: [`--user-data-dir=${profilePath}`],
      cwd: path.dirname(executablePath),
      env: launchEnv,
    });
    const page = await app.firstWindow();
    page.on("console", (message) => {
      if (message.type() === "error") result.console_errors.push(message.text());
    });
    page.on("pageerror", (error) => result.page_errors.push(String(error.message || error)));
    page.on("request", (request) => {
      const url = request.url();
      if (!/^http:\/\/127\.0\.0\.1:\d+\//.test(url) && !url.startsWith("data:")) {
        result.external_requests.push(url);
      }
    });
    await page.waitForURL(/http:\/\/127\.0\.0\.1:\d+\/desktop/, { timeout: 120000 });
    const base = new URL(page.url()).origin;
    await page.goto(`${base}/desktop?view=extensions`);
    await page.locator('[data-agent-skill-market="true"]').waitFor({ timeout: 60000 });
    await page.locator('[data-capability-type="cli"]').click();
    const panel = page.locator('#deepseekHarnessPanel');
    await panel.waitFor({ state: "visible", timeout: 30000 });
    assert.match(await panel.innerText(), /DeepSeek Harness 官方开源底座/);
    const marketData = await page.locator('#agentSkillMarketData').evaluate((node) => JSON.parse(node.textContent || '{}'));
    assert.equal(marketData.connections.deepseek_harness.version, '0.1.0-rc.6');
    await page.locator('#deepseekHarnessTarget').selectOption('project|apparel-growth');
    assert.equal(await page.locator('#prepareDeepseekHarness').isEnabled(), true);
    assert.equal(await page.locator('#openDeepseekHarness').isEnabled(), true);
    await page.locator('#prepareDeepseekHarness').click();
    await page.locator('#deepseekHarnessStatus[data-state="ok"]').waitFor({ timeout: 30000 });

    const integrationRoot = path.join(workspace, 'projects', 'apparel-growth', '.tone', 'deepseek-harness');
    const patchPath = path.join(integrationRoot, 'tone-mcp.patch.yml');
    const manifestPath = path.join(integrationRoot, 'integration.json');
    assert.equal(fs.existsSync(patchPath), true, 'project Harness patch is missing');
    assert.equal(fs.existsSync(manifestPath), true, 'project Harness manifest is missing');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    assert.equal(manifest.harness.official_repository, true);
    assert.equal(manifest.harness.license, 'MIT');
    assert.equal(manifest.mcp_server.args[0], 'harness-mcp');
    assert.match(manifest.mcp_server.command, /t-one-runtime\.exe$/i);

    const opened = await page.evaluate(async () => window.teelabDesktop.invoke(
      'open_deepseek_harness',
      { item_type: 'project', item_id: 'apparel-growth', owner_confirmed: true, port: 3108 },
    ));
    assert.equal(opened.ok, true, opened.error || 'Harness did not start');
    harnessPort = Number(new URL(opened.url).port);
    assert.equal(await portIsOpen(harnessPort), true);
    result.harness = {
      official_repository: true,
      installed_version: manifest.harness.version,
      mcp_transport: manifest.transport,
      packaged_runtime_mcp: true,
      project_registered: true,
      project_id: 'apparel-growth',
      tool_namespace: manifest.tool_namespace,
      port: harnessPort,
    };
    await panel.scrollIntoViewIfNeeded();
    await page.screenshot({ path: screenshotPath, fullPage: false });
    await page.goto(opened.url);
    await page.waitForLoadState('domcontentloaded');
    assert.equal(await page.title(), 'DeepSeek Harness');
    const workspaceList = await page.evaluate(async () => {
      const response = await fetch('/api/workspace.list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'client-request',
          rpcId: `tone-formal-${Date.now()}`,
          method: 'workspace.list',
          payload: {},
        }),
      });
      return response.json();
    });
    assert.equal(workspaceList.result.ok, true);
    assert.equal(
      workspaceList.result.value.items.some((item) => item.title === 'apparel-growth'),
      true,
      'Harness did not retain the selected T One project workspace',
    );
    assert.deepEqual(result.console_errors, []);
    assert.deepEqual(result.page_errors, []);
    assert.deepEqual(result.external_requests, []);
    result.ok = true;
  } finally {
    if (app) await app.close().catch(() => {});
    result.harness_port_closed = harnessPort ? await waitForPortClosed(harnessPort) : false;
    fs.mkdirSync(artifactRoot, { recursive: true });
    fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
    await fs.promises.rm(profileRoot, { recursive: true, force: true, maxRetries: 4, retryDelay: 250 }).catch(() => {});
  }
  assert.equal(result.harness_port_closed, true);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || error}\n`);
  process.exitCode = 1;
});
