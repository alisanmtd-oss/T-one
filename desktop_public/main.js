const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { app, BrowserWindow, dialog, ipcMain, safeStorage, shell } = require("electron");

const APP_TITLE = "T One 中文社区版";

function cleanText(value, max = 120) {
  return String(value || "").replace(/[\u0000-\u001f<>:"/\\|?*]/g, " ").trim().slice(0, max);
}

function safeValue(value, max = 500) {
  return String(value || "").replace(/\u0000/g, "").trim().slice(0, max);
}

function makeId(prefix, name) {
  const slug = cleanText(name, 48).toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-").replace(/^-|-$/g, "") || prefix;
  return `${slug}-${Date.now().toString(36)}`;
}

function workspaceRoot() {
  return path.join(app.getPath("userData"), "TOneWorkspace");
}

function statePath() {
  return path.join(workspaceRoot(), "workspace.json");
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temporary = `${filePath}.tmp`;
  fs.writeFileSync(temporary, JSON.stringify(value, null, 2), "utf8");
  fs.renameSync(temporary, filePath);
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function loadState() {
  fs.mkdirSync(workspaceRoot(), { recursive: true });
  const state = readJson(statePath(), { schemaVersion: 1, projects: [], connections: [] });
  state.projects = Array.isArray(state.projects) ? state.projects : [];
  state.connections = Array.isArray(state.connections) ? state.connections : [];
  state.workspacePath = workspaceRoot();
  return state;
}

function saveState(state) {
  const copy = { schemaVersion: 1, projects: state.projects || [], connections: state.connections || [] };
  writeJson(statePath(), copy);
}

function projectFolder(projectId) {
  return path.join(workspaceRoot(), "projects", cleanText(projectId, 80));
}

function taskFolder(projectId, taskId) {
  return path.join(projectFolder(projectId), "tasks", cleanText(taskId, 80));
}

function findProject(state, projectId) {
  return state.projects.find((item) => item.id === projectId);
}

function findTask(state, projectId, taskId) {
  const project = findProject(state, projectId);
  return { project, task: project?.tasks?.find((item) => item.id === taskId) };
}

function hydrate(state) {
  for (const project of state.projects) {
    project.folder = projectFolder(project.id);
    for (const task of project.tasks || []) {
      const folder = taskFolder(project.id, task.id);
      task.folder = folder;
      task.messages = readJson(path.join(folder, "messages.json"), []);
      const inputs = path.join(folder, "inputs");
      task.files = fs.existsSync(inputs)
        ? fs.readdirSync(inputs, { withFileTypes: true }).filter((entry) => entry.isFile()).map((entry) => entry.name)
        : [];
    }
  }
  state.connections = state.connections.map(({ secretEncrypted, ...item }) => item);
  return state;
}

function parseArguments(value) {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) throw new Error();
    return parsed.slice(0, 30);
  } catch {
    throw new Error("CLI 参数必须是 JSON 数组，例如 [\"exec\",\"-\"]");
  }
}

function runProcess(command, args, options, input) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { ...options, windowsHide: true, shell: false });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(new Error("CLI 运行超过 5 分钟，已停止等待"));
    }, 300000);
    child.stdout.on("data", (chunk) => { stdout = (stdout + chunk.toString()).slice(-2_000_000); });
    child.stderr.on("data", (chunk) => { stderr = (stderr + chunk.toString()).slice(-500_000); });
    child.on("error", (error) => finish(error));
    child.on("close", (exitCode) => finish(null, { exitCode, stdout, stderr }));
    child.stdin.end(input || "");
  });
}

function usefulCliOutput(stdout) {
  const messages = [];
  for (const line of String(stdout || "").split(/\r?\n/)) {
    try {
      const event = JSON.parse(line);
      const item = event.item || event.data || {};
      const text = item.text || item.content || event.result || "";
      if ((item.type === "agent_message" || event.type === "result") && typeof text === "string") messages.push(text);
    } catch {
      // Plain-text CLIs are returned below without pretending they are JSONL.
    }
  }
  return safeValue(messages.join("\n\n") || stdout, 12000);
}

function registerWorkspaceHandlers() {
  ipcMain.handle("workspace:load", () => hydrate(loadState()));

  ipcMain.handle("project:create", (_event, payload = {}) => {
    const name = cleanText(payload.name);
    if (!name) throw new Error("项目名称不能为空");
    const state = loadState();
    const project = { id: makeId("project", name), name, description: cleanText(payload.description, 300), createdAt: new Date().toISOString(), tasks: [] };
    state.projects.unshift(project);
    const folder = projectFolder(project.id);
    for (const child of ["tasks", "shared", "knowledge", "exports"]) fs.mkdirSync(path.join(folder, child), { recursive: true });
    writeJson(path.join(folder, "project.json"), project);
    saveState(state);
    return hydrate(state);
  });

  ipcMain.handle("task:create", (_event, payload = {}) => {
    const state = loadState();
    const project = findProject(state, payload.projectId);
    const name = cleanText(payload.name);
    if (!project) throw new Error("没有找到项目");
    if (!name) throw new Error("任务名称不能为空");
    const task = { id: makeId("task", name), name, status: "进行中", createdAt: new Date().toISOString(), capabilities: [] };
    project.tasks = Array.isArray(project.tasks) ? project.tasks : [];
    project.tasks.unshift(task);
    const folder = taskFolder(project.id, task.id);
    for (const child of ["inputs", "results", "receipts", "memory"]) fs.mkdirSync(path.join(folder, child), { recursive: true });
    writeJson(path.join(folder, "task.json"), task);
    writeJson(path.join(folder, "messages.json"), []);
    writeJson(path.join(projectFolder(project.id), "project.json"), project);
    saveState(state);
    return hydrate(state);
  });

  ipcMain.handle("task:save-messages", (_event, payload = {}) => {
    const state = loadState();
    const { project, task } = findTask(state, payload.projectId, payload.taskId);
    if (!project || !task) throw new Error("没有找到任务");
    const messages = (Array.isArray(payload.messages) ? payload.messages : []).slice(-500).map((item) => ({
      role: item.role === "user" ? "user" : "assistant",
      text: safeValue(item.text, 12000),
      at: safeValue(item.at, 40) || new Date().toISOString(),
    }));
    writeJson(path.join(taskFolder(project.id, task.id), "messages.json"), messages);
    task.updatedAt = new Date().toISOString();
    saveState(state);
    return { ok: true };
  });

  ipcMain.handle("task:choose-files", async (_event, payload = {}) => {
    const state = loadState();
    const { project, task } = findTask(state, payload.projectId, payload.taskId);
    if (!project || !task) throw new Error("请先选择任务");
    const selection = await dialog.showOpenDialog(BrowserWindow.getFocusedWindow() || undefined, { properties: ["openFile", "multiSelections"] });
    if (selection.canceled) return hydrate(state);
    const target = path.join(taskFolder(project.id, task.id), "inputs");
    fs.mkdirSync(target, { recursive: true });
    for (const source of selection.filePaths) {
      const base = cleanText(path.basename(source), 180) || "file";
      let destination = path.join(target, base);
      if (fs.existsSync(destination)) destination = path.join(target, `${Date.now()}-${base}`);
      fs.copyFileSync(source, destination);
    }
    return hydrate(state);
  });

  ipcMain.handle("capability:assign", (_event, payload = {}) => {
    const state = loadState();
    const { project, task } = findTask(state, payload.projectId, payload.taskId);
    if (!project || !task) throw new Error("请先选择任务");
    const id = cleanText(payload.capabilityId, 80);
    task.capabilities = Array.isArray(task.capabilities) ? task.capabilities : [];
    task.capabilities = task.capabilities.includes(id) ? task.capabilities.filter((item) => item !== id) : [...task.capabilities, id];
    writeJson(path.join(taskFolder(project.id, task.id), "task.json"), task);
    saveState(state);
    return hydrate(state);
  });

  ipcMain.handle("task:set-executor", (_event, payload = {}) => {
    const state = loadState();
    const { project, task } = findTask(state, payload.projectId, payload.taskId);
    if (!project || !task) throw new Error("请先选择任务");
    const connection = state.connections.find((item) => item.id === payload.connectionId && item.type === "cli" && item.status === "detected");
    task.executorId = connection ? connection.id : "";
    writeJson(path.join(taskFolder(project.id, task.id), "task.json"), task);
    saveState(state);
    return hydrate(state);
  });

  ipcMain.handle("project:open-folder", async (_event, payload = {}) => {
    const state = loadState();
    const project = findProject(state, payload.projectId);
    if (!project) throw new Error("没有找到项目");
    const error = await shell.openPath(projectFolder(project.id));
    return { ok: !error, error };
  });

  ipcMain.handle("connection:save", (_event, payload = {}) => {
    const type = payload.type === "cli" ? "cli" : "mcp";
    const name = cleanText(payload.name);
    const target = safeValue(payload.target, 500);
    if (!name || !target) throw new Error("名称和地址/命令不能为空");
    const state = loadState();
    const record = {
      id: makeId(type, name), type, name, target,
      arguments: type === "cli" ? JSON.stringify(parseArguments(payload.arguments)) : "[]",
      secretHeader: cleanText(payload.secretHeader || "Authorization", 80),
      status: "saved_unverified", createdAt: new Date().toISOString(), hasSecret: false,
    };
    const secret = String(payload.secret || "");
    if (secret) {
      if (!safeStorage.isEncryptionAvailable()) throw new Error("当前系统无法安全保存凭据，请不要输入 Token");
      record.secretEncrypted = safeStorage.encryptString(secret).toString("base64");
      record.hasSecret = true;
    }
    state.connections.push(record);
    saveState(state);
    return hydrate(state);
  });

  ipcMain.handle("connection:detect-cli", async (_event, payload = {}) => {
    const state = loadState();
    const connection = state.connections.find((item) => item.id === payload.connectionId && item.type === "cli");
    if (!connection) throw new Error("没有找到 CLI");
    const command = connection.target;
    const detectedPath = path.isAbsolute(command) && fs.existsSync(command)
      ? command
      : await new Promise((resolve) => {
          const child = spawn("where.exe", [command], { windowsHide: true, shell: false });
          let output = "";
          child.stdout.on("data", (chunk) => { output += chunk.toString(); });
          child.on("error", () => resolve(""));
          child.on("close", (code) => resolve(code === 0 ? output.split(/\r?\n/).find(Boolean) || "" : ""));
        });
    connection.status = detectedPath ? "detected" : "not_detected";
    connection.detectedPath = safeValue(detectedPath, 500);
    connection.checkedAt = new Date().toISOString();
    saveState(state);
    return hydrate(state);
  });

  ipcMain.handle("connection:test-mcp", async (_event, payload = {}) => {
    const state = loadState();
    const connection = state.connections.find((item) => item.id === payload.connectionId && item.type === "mcp");
    if (!connection) throw new Error("没有找到 MCP");
    let url;
    try { url = new URL(connection.target); } catch { throw new Error("MCP URL 无效"); }
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error("MCP 只允许 HTTP 或 HTTPS 地址");
    const headers = { "Content-Type": "application/json", Accept: "application/json, text/event-stream" };
    if (connection.secretEncrypted) {
      const secret = safeStorage.decryptString(Buffer.from(connection.secretEncrypted, "base64"));
      headers[connection.secretHeader || "Authorization"] = (connection.secretHeader || "Authorization").toLowerCase() === "authorization" ? `Bearer ${secret}` : secret;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(url, {
        method: "POST", headers, signal: controller.signal,
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "t-one-community", version: "0.5.0" } } }),
      });
      connection.status = response.ok ? "mcp_reachable" : "mcp_failed";
      connection.checkedAt = new Date().toISOString();
      connection.lastHttpStatus = response.status;
      saveState(state);
      if (!response.ok) throw new Error(`MCP 返回 HTTP ${response.status}`);
      return hydrate(state);
    } catch (error) {
      connection.status = "mcp_failed";
      connection.checkedAt = new Date().toISOString();
      saveState(state);
      throw new Error(error.name === "AbortError" ? "MCP 连通测试超时" : `MCP 连通失败：${error.message}`);
    } finally {
      clearTimeout(timer);
    }
  });

  ipcMain.handle("task:run-cli", async (_event, payload = {}) => {
    const state = loadState();
    const { project, task } = findTask(state, payload.projectId, payload.taskId);
    if (!project || !task) throw new Error("请先选择任务");
    const connection = state.connections.find((item) => item.id === payload.connectionId && item.type === "cli");
    if (!connection || connection.status !== "detected") throw new Error("请选择已检测的 CLI");
    const prompt = safeValue(payload.prompt, 12000);
    if (!prompt) throw new Error("任务指令不能为空");
    let args = parseArguments(connection.arguments);
    const commandName = path.basename(connection.detectedPath || connection.target).toLowerCase();
    if (!args.length && /^codex(?:\.exe|\.cmd)?$/.test(commandName)) args = ["exec", "--json", "--skip-git-repo-check", "-"];
    const usesPromptArgument = args.some((item) => item.includes("{prompt}"));
    const capabilityNames = Array.isArray(payload.capabilityNames) ? payload.capabilityNames.map((item) => cleanText(item, 100)).filter(Boolean).slice(0, 5) : [];
    const scopedPrompt = `项目：${project.name}\n任务：${task.name}\n任务目录：${taskFolder(project.id, task.id)}\n已选能力：${capabilityNames.join("、") || "无"}\n\n用户指令：\n${prompt}\n\n只处理当前任务目录；如需外部发布、花费、付款、发货、退款或账号授权，先返回需要确认的草稿，不要自行执行。`;
    args = args.map((item) => item.replaceAll("{prompt}", scopedPrompt));
    const startedAt = new Date().toISOString();
    const result = await runProcess(connection.detectedPath || connection.target, args, {
      cwd: taskFolder(project.id, task.id),
      env: process.env,
    }, usesPromptArgument ? "" : scopedPrompt);
    const output = usefulCliOutput(result.stdout);
    const receipt = {
      connectionId: connection.id, connectionName: connection.name, command: connection.target,
      args, startedAt, finishedAt: new Date().toISOString(), exitCode: result.exitCode,
      output, stderr: safeValue(result.stderr, 4000),
    };
    const receiptPath = path.join(taskFolder(project.id, task.id), "results", `cli-${Date.now()}.json`);
    writeJson(receiptPath, receipt);
    if (result.exitCode !== 0) throw new Error(receipt.stderr || `CLI 退出码 ${result.exitCode}`);
    if (!output) throw new Error("CLI 已退出但没有真实输出，未生成完成回复");
    return { ok: true, output, receiptPath };
  });

  ipcMain.handle("connection:remove", (_event, payload = {}) => {
    const state = loadState();
    state.connections = state.connections.filter((item) => item.id !== payload.connectionId);
    saveState(state);
    return hydrate(state);
  });
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1240,
    height: 800,
    minWidth: 980,
    minHeight: 640,
    title: APP_TITLE,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event, url) => {
    if (url !== window.webContents.getURL()) event.preventDefault();
  });
  window.loadFile(path.join(__dirname, "ui", "index.html"));
  return window;
}

app.whenReady().then(() => {
  app.setAppUserModelId("org.tone.community.desktop");
  registerWorkspaceHandlers();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
