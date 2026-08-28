const assert = require("node:assert/strict");
const fs = require("node:fs");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { _electron: electron } = require(process.env.TONE_PLAYWRIGHT_PACKAGE || "playwright");

async function removeProfileRoot(profileRoot) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      await fs.promises.rm(profileRoot, { recursive: true, force: true, maxRetries: 2, retryDelay: 250 });
      if (!fs.existsSync(profileRoot)) return true;
    } catch (_error) {
      // Chromium can release a profile lock a few milliseconds after app.close().
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return !fs.existsSync(profileRoot);
}

const executablePath = process.env.TONE_PUBLIC_EXECUTABLE;
assert.ok(executablePath && fs.existsSync(executablePath), "TONE_PUBLIC_EXECUTABLE must point to the unpacked public T-one.exe");

const artifactRoot = process.env.TONE_PUBLIC_ARTIFACT_ROOT || path.join(os.tmpdir(), "t-one-public-formal-acceptance");
const profileRoot = fs.mkdtempSync(path.join(os.tmpdir(), "t-one-public-profile-"));
const workspace = path.join(profileRoot, "profile", "workspace");
fs.mkdirSync(artifactRoot, { recursive: true });
const screenshotPath = path.join(artifactRoot, "public-formal-market.png");
const creationScreenshotPath = path.join(artifactRoot, "public-formal-workspace-creation.png");

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

async function waitForWorkspaceNavigation(page, pattern, statusSelector) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (pattern.test(page.url())) return;
    const state = await page.locator(statusSelector).getAttribute('data-state').catch(() => '');
    const message = await page.locator(statusSelector).innerText().catch(() => '');
    if (state === 'error') throw new Error(`${statusSelector}: ${message}`);
    await page.waitForTimeout(150);
  }
  const message = await page.locator(statusSelector).innerText().catch(() => '');
  throw new Error(`${statusSelector} did not navigate: ${message}`);
}

function attachDiagnostics(page, result) {
  page.on("console", (message) => {
    if (message.type() === "error") result.console_errors.push(message.text());
  });
  page.on("pageerror", (error) => result.page_errors.push(String(error.message || error)));
  page.on("response", (response) => {
    if (response.status() >= 400) result.http_errors.push({ status: response.status(), url: response.url() });
  });
  page.on("request", (request) => {
    const url = request.url();
    if (!/^http:\/\/127\.0\.0\.1:\d+\//.test(url) && !url.startsWith("data:")) result.external_requests.push(url);
  });
}

async function waitForPortRelease(port) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline && await portIsOpen(port)) {
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  assert.equal(await portIsOpen(port), false, `bundled backend port ${port} remained open after app exit`);
}

async function auditCurrentPage(page, result, label) {
  const duplicateIds = await page.locator('[id]').evaluateAll((nodes) => {
    const counts = new Map();
    for (const node of nodes) counts.set(node.id, (counts.get(node.id) || 0) + 1);
    return [...counts.entries()].filter(([, count]) => count > 1);
  });
  const emptyButtons = await page.locator('button:visible:not(:disabled)').evaluateAll((nodes) => nodes
    .filter((node) => !(node.innerText || node.getAttribute('aria-label') || node.getAttribute('title') || '').trim())
    .map((node) => node.id || node.outerHTML.slice(0, 160)));
  const brokenAnchors = await page.locator('a:visible').evaluateAll((nodes) => nodes
    .map((node) => node.getAttribute('href'))
    .filter((href) => href === '' || href === '#' || /^javascript:/i.test(href || '')));
  assert.deepEqual(duplicateIds, [], `${label}: duplicate ids`);
  assert.deepEqual(emptyButtons, [], `${label}: visible enabled buttons without a name`);
  assert.deepEqual(brokenAnchors, [], `${label}: empty or script-only links`);
  const base = new URL(page.url()).origin;
  const localLinks = await page.locator('a:visible').evaluateAll((nodes, origin) => [...new Set(nodes
    .map((node) => node.href)
    .filter((href) => {
      try {
        const url = new URL(href);
        return url.origin === origin
          && !url.pathname.startsWith('/api/')
          && !url.pathname.startsWith('/download/')
          && !url.pathname.toLowerCase().includes('amazon');
      } catch (_error) { return false; }
    }))], base);
  for (const href of localLinks) {
    const response = await page.request.get(href, { maxRedirects: 0 });
    assert.ok(response.status() >= 200 && response.status() < 400, `${label}: ${href} returned ${response.status()}`);
  }
  result.route_audit[label] = {
    duplicate_ids: 0,
    empty_buttons: 0,
    broken_anchors: 0,
    local_links_checked: localLinks.length,
  };
}

function runPackagedCli(runtime, workspaceRoot, ...arguments) {
  const completed = spawnSync(runtime, ['cli', '--root', workspaceRoot, '--', '--json', ...arguments], {
    cwd: path.dirname(runtime),
    encoding: 'utf8',
    windowsHide: true,
  });
  assert.equal(completed.status, 0, completed.stderr || completed.stdout || 'packaged CLI failed');
  return JSON.parse(completed.stdout);
}

async function main() {
  const result = { ok: false, console_errors: [], page_errors: [], http_errors: [], external_requests: [], counts: {} };
  const launchEnv = { ...process.env, TONE_E2E_ALLOW_PARALLEL: "1" };
  delete launchEnv.TEELAB_AGENT_ROOT;
  delete launchEnv.TEELAB_AGENT_PYTHON;
  delete launchEnv.PYTHONPATH;
  let app;
  let port = 0;
  try {
    app = await electron.launch({
      executablePath,
      args: [`--user-data-dir=${path.join(profileRoot, "profile")}`],
      cwd: path.dirname(executablePath),
      env: launchEnv,
    });
    let page = await app.firstWindow();
    await app.evaluate(({ BrowserWindow }) => {
      const window = BrowserWindow.getAllWindows()[0];
      if (window) window.setSize(1100, 720);
    });
    attachDiagnostics(page, result);
    await page.waitForURL(/http:\/\/127\.0\.0\.1:\d+\/desktop/, { timeout: 120000 });
    port = Number(new URL(page.url()).port);
    result.counts.project_sections = await page.locator("details[data-project-section]").count();
    result.counts.market_navigation = await page.locator('[data-capability-market-nav="true"]').count();
    assert.ok(result.counts.project_sections > 0, "formal project sidebar is missing");
    assert.ok(result.counts.market_navigation > 0, "formal capability-market navigation is missing");

    const base = new URL(page.url()).origin;
    await page.goto(`${base}/desktop?view=new`);
    await page.locator('#newProjectPickerButton').waitFor({ state: 'visible', timeout: 30000 });
    const suffix = Date.now().toString(36);
    const projectName = `安装版验收项目 ${suffix}`;
    const taskName = `安装版验收任务 ${suffix}`;
    const initialInstruction = `${taskName}；不执行外部店铺动作`;
    await page.locator('#newProjectPickerButton').click();
    await page.locator('#showInlineProjectCreate').click();
    await page.locator('#inlineProjectName').fill(projectName);
    await page.locator('#saveInlineProject').click();
    await page.waitForFunction((name) => {
      const select = document.getElementById('newProject');
      return select && select.value && select.selectedOptions[0]?.textContent === name;
    }, projectName, { timeout: 30000 });
    const projectId = await page.locator('#newProject').inputValue();
    assert.ok(projectId, 'public installer did not return a project id');
    await page.locator('#newConversationTarget').selectOption('workstream', { force: true });
    await page.locator('#newConversationTarget').dispatchEvent('change');
    await page.locator('#message').fill(initialInstruction);
    await page.route('**/desktop?*', async (route) => {
      const url = new URL(route.request().url());
      if (url.searchParams.get('autostart') === '1') {
        url.searchParams.delete('autostart');
        await route.continue({ url: url.toString() });
        return;
      }
      await route.continue();
    });
    await page.locator('#send').click();
    await page.waitForURL(/\?project=project-[^&]+&task=task-[^&]+$/, { timeout: 30000 });
    const taskId = new URL(page.url()).searchParams.get('task');
    assert.ok(taskId, 'public installer did not return a task id');
    const projectManifest = path.join(workspace, 'projects', projectId, 'project.json');
    const taskManifest = path.join(workspace, 'projects', projectId, 'tasks', taskId, 'task.json');
    assert.equal(fs.existsSync(projectManifest), true, 'public installer project manifest is missing');
    assert.equal(fs.existsSync(taskManifest), true, 'public installer task manifest is missing');
    assert.equal(JSON.parse(fs.readFileSync(projectManifest, 'utf8')).name, projectName);
    let taskManifestPayload = JSON.parse(fs.readFileSync(taskManifest, 'utf8'));
    assert.equal(taskManifestPayload.name, taskName);
    assert.equal(taskManifestPayload.initial_instruction, initialInstruction);
    await page.locator('[data-task-workflow-guide="true"]').waitFor({ state: 'visible', timeout: 30000 });
    assert.equal(await page.locator('#taskWorkflowObjective').textContent(), initialInstruction);
    await page.locator('[data-workspace-open-folder="true"]:visible').waitFor({
      state: 'visible',
      timeout: 10000,
    });
    assert.equal(await page.locator('[data-workspace-open-folder="true"]:visible').count(), 1);

    const revisedInstruction = '确认目标，选择能力，在本地执行，再从历史结果继续。';
    await page.locator('#taskWorkflowEditGoal').click();
    await page.locator('#taskBriefInstruction').fill(revisedInstruction);
    await page.locator('#saveTaskBrief').click();
    await page.locator('#taskBriefDialog').waitFor({ state: 'hidden', timeout: 10000 });
    await page.locator('#taskWorkflowCapabilities').click();
    await page.locator('[data-agent-skill-market="true"]').waitFor({ timeout: 60000 });
    assert.equal(await page.locator('#agentSkillTargetTask').inputValue(), taskId);
    assert.equal(await page.locator('[data-return-to-task="true"]:visible').count(), 1);
    await page.locator('[data-capability-type="agent"]').click();
    const agentChoice = page.locator('[data-agent-skill-choice="agent"]:not(:disabled)').first();
    await agentChoice.waitFor({ state: 'visible', timeout: 30000 });
    const selectedAgent = await agentChoice.getAttribute('value');
    await agentChoice.check();
    await page.locator('#saveAgentSkillSelection').click();
    await page.waitForURL(/\?project=project-[^&]+&task=task-[^&]+$/, { timeout: 30000 });
    await page.locator('[data-task-workflow-guide="true"]').waitFor({ state: 'visible', timeout: 30000 });
    assert.match(await page.locator('#taskWorkflowCapabilityState').textContent(), /1 Agent/);
    assert.equal(await page.locator('.topbar .status').textContent(), '待执行');
    await page.locator('#taskWorkflowStart').click();
    await page.waitForTimeout(350);
    assert.equal(await page.evaluate(() => document.activeElement?.id), 'message');
    assert.equal(await page.locator('#message').inputValue(), revisedInstruction);
    await page.locator('#taskWorkflowResults').click();
    await page.locator('[data-history-context="true"][open]').waitFor({ timeout: 10000 });
    taskManifestPayload = JSON.parse(fs.readFileSync(taskManifest, 'utf8'));
    assert.equal(taskManifestPayload.initial_instruction, revisedInstruction);
    assert.deepEqual(taskManifestPayload.toolkit.agents, [selectedAgent]);
    assert.equal(taskManifestPayload.status, '待执行');
    result.workspace_creation = {
      project_id: projectId,
      task_id: taskId,
      project_manifest_verified: true,
      task_manifest_verified: true,
      middle_workflow_verified: true,
      selected_agent: selectedAgent,
      task_status: taskManifestPayload.status,
      external_store_actions: 0,
    };
    await page.screenshot({ path: creationScreenshotPath, fullPage: false });

    const marketHref = await page.locator('[data-capability-market-nav="true"]').first().getAttribute("href");
    await page.goto(new URL(marketHref, page.url()).toString());
    await page.locator('[data-agent-skill-market="true"]').waitFor({ timeout: 60000 });
    for (const kind of ["agent", "skill", "mcp", "cli"]) {
      await page.locator(`[data-capability-type="${kind}"]`).click();
      result.counts[kind] = await page.locator(`[data-market-kind="${kind}"]`).count();
      assert.ok(result.counts[kind] > 0, `${kind} marketplace category is empty`);
    }
    await page.screenshot({ path: screenshotPath, fullPage: true });

    await page.goto(`${base}/desktop?view=settings`);
    await page.locator('[data-settings-page-nav="settings-skills-agents"]').click();
    await page.locator('[data-open-tool-registry="true"]').waitFor({ timeout: 60000 });
    result.counts.open_tool_registry = await page.locator('[data-open-tool-registry="true"]').count();
    result.counts.cli_roundtrip = await page.locator('[data-cli-ai-roundtrip="true"]').count();
    assert.equal(result.counts.open_tool_registry, 1);
    assert.equal(result.counts.cli_roundtrip, 1);

    result.route_audit = {};
    const coreRoutes = {
      new: '/desktop?view=new',
      realtime: '/desktop?view=dashboard',
      modules: '/desktop?view=module_dashboard',
      market: '/desktop?view=extensions',
      settings: '/desktop?view=settings',
      project: `/desktop?project=${encodeURIComponent(projectId)}`,
      task: `/desktop?project=${encodeURIComponent(projectId)}&task=${encodeURIComponent(taskId)}`,
    };
    for (const [label, route] of Object.entries(coreRoutes)) {
      const response = await page.goto(`${base}${route}`);
      assert.equal(response?.status(), 200, `${label} route did not return 200`);
      await page.locator('body[data-desktop-ui="true"]').waitFor({ timeout: 60000 });
      await auditCurrentPage(page, result, label);
    }
    const retiredRoutes = {
      '/': '/desktop?view=dashboard',
      '/dashboard': '/desktop?view=dashboard',
      '/selection': '/desktop?view=dashboard',
      '/selection-intelligence': '/desktop?view=dashboard',
      '/selection-meeting': '/desktop?view=dashboard',
      '/b2b-sales': '/desktop?view=dashboard',
      '/chat': '/desktop?view=new',
      '/realtime-big-screen': '/desktop?view=module_dashboard',
      '/store-erp': '/desktop?view=erp_cost',
      '/help-center': '/desktop?view=settings',
    };
    for (const [route, expected] of Object.entries(retiredRoutes)) {
      const response = await page.request.get(`${base}${route}`, { maxRedirects: 0 });
      assert.equal(response.status(), 302, `${route} should redirect`);
      assert.equal(response.headers().location, expected, `${route} redirects to the wrong current surface`);
    }
    result.retired_routes = Object.keys(retiredRoutes).length;

    await page.goto(`${base}/desktop?project=${encodeURIComponent(projectId)}&task=${encodeURIComponent(taskId)}`);
    await page.locator('[data-task-workflow-guide="true"]').waitFor({ timeout: 60000 });
    await app.close();
    app = undefined;
    await waitForPortRelease(port);
    result.first_port_released = true;
    port = 0;

    app = await electron.launch({
      executablePath,
      args: [`--user-data-dir=${path.join(profileRoot, "profile")}`],
      cwd: path.dirname(executablePath),
      env: launchEnv,
    });
    page = await app.firstWindow();
    attachDiagnostics(page, result);
    await page.waitForURL(/http:\/\/127\.0\.0\.1:\d+\/desktop/, { timeout: 120000 });
    port = Number(new URL(page.url()).port);
    const restartedBase = new URL(page.url()).origin;
    await page.goto(`${restartedBase}/desktop?project=${encodeURIComponent(projectId)}&task=${encodeURIComponent(taskId)}`);
    await page.locator('[data-task-workflow-guide="true"]').waitFor({ timeout: 60000 });
    assert.equal(await page.locator('#taskWorkflowObjective').textContent(), revisedInstruction);
    assert.match(await page.locator('#taskWorkflowCapabilityState').textContent(), /1 Agent/);
    assert.equal(await page.locator('.topbar .status').textContent(), '待执行');
    await page.locator('#taskWorkflowStart').click();
    assert.equal(await page.locator('#message').inputValue(), revisedInstruction);
    await page.locator('#taskWorkflowResults').click();
    await page.locator('[data-history-context="true"][open]').waitFor({ timeout: 10000 });
    result.restart_recovery = {
      project_id: projectId,
      task_id: taskId,
      goal: true,
      capability: true,
      status: true,
      execution_input: true,
      history: true,
    };
    const packagedRuntime = path.join(path.dirname(executablePath), 'resources', 't-one-runtime', 't-one-runtime.exe');
    assert.equal(fs.existsSync(packagedRuntime), true, 'packaged CLI runtime is missing');
    const cliStatus = runPackagedCli(packagedRuntime, workspace, 'status');
    const cliProject = runPackagedCli(packagedRuntime, workspace, 'workspace', 'show', '--project', projectId);
    const cliTask = runPackagedCli(packagedRuntime, workspace, 'workspace', 'show', '--task', taskId);
    assert.equal(cliStatus.version, '0.5.9');
    assert.equal(cliProject.project.id, projectId);
    assert.equal(cliProject.project.manifest_exists, true);
    assert.equal(cliTask.task.id, taskId);
    assert.equal(cliTask.task.initial_instruction, revisedInstruction);
    assert.deepEqual(cliTask.task.toolkit.agents, [selectedAgent]);
    assert.equal(cliTask.task.manifest_exists, true);
    assert.equal(cliTask.external_actions, 0);
    result.cli_workspace_readback = {
      version: cliStatus.version,
      project: true,
      task: true,
      goal: true,
      capability: true,
      local_manifests: true,
      external_actions: 0,
    };
    if (result.console_errors.length || result.page_errors.length || result.http_errors.length || result.external_requests.length) {
      process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    }
    assert.deepEqual(result.console_errors, []);
    assert.deepEqual(result.page_errors, []);
    assert.deepEqual(result.external_requests, []);

    assert.ok(fs.existsSync(path.join(workspace, "config", "workspace_projects.json")), "first-run workspace was not seeded");
    result.workspace_seeded = true;
    result.screenshot = screenshotPath;
    result.workspace_creation_screenshot = creationScreenshotPath;
    result.port = port;
    result.ok = true;
    if (process.env.TONE_PUBLIC_RESULT_PATH) {
      fs.mkdirSync(path.dirname(process.env.TONE_PUBLIC_RESULT_PATH), { recursive: true });
      fs.writeFileSync(process.env.TONE_PUBLIC_RESULT_PATH, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
    }
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } finally {
    if (app) await app.close().catch(() => {});
    if (port) {
      await waitForPortRelease(port);
    }
    const profileRemoved = await removeProfileRoot(profileRoot);
    if (!profileRemoved) {
      process.stderr.write(`Warning: temporary profile cleanup is still pending: ${profileRoot}\n`);
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
