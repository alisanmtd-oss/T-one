const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const net = require("net");
const path = require("path");
const readline = require("readline");
const { HOME_PATH, resolveStartupPath } = require("./startup-route");
const {
  backendStatusIsCompatible,
  computeBackendSourceSignature
} = require("./backend-compatibility");

const LEGACY_USER_DATA_PATH = path.join(app.getPath("appData"), "teelab-commerce-agent-desktop");
const hasExplicitUserDataDir = process.argv.some((argument) =>
  /^--user-data-dir(?:=|$)/i.test(String(argument || "")),
);
if (!hasExplicitUserDataDir && fs.existsSync(LEGACY_USER_DATA_PATH)) {
  app.setPath("userData", LEGACY_USER_DATA_PATH);
}

const CONFIG_PATH = path.join(__dirname, "app-config.json");
const USER_CONFIG_PATH = path.join(app.getPath("userData"), "app-config.json");
const WORKSPACE_LOCATOR_NAME = "teelab-agent-root.json";
const DEFAULT_CONFIG = {
  project_root: "",
  backend_port: 8767,
  start_path: HOME_PATH,
  python_executable: ""
};
const BRIDGE_PREFIX = "__TEELAB_BRIDGE__";

function loadOrCreateDesktopAuthToken() {
  const tokenPath = path.join(app.getPath("userData"), "desktop-auth-token");
  try {
    const existing = fs.readFileSync(tokenPath, "utf8").trim();
    if (/^[a-f0-9]{64}$/i.test(existing)) return existing;
  } catch (_error) {
    // First launch creates one local token that later launches can reuse.
  }
  const token = crypto.randomBytes(32).toString("hex");
  fs.mkdirSync(path.dirname(tokenPath), { recursive: true });
  fs.writeFileSync(tokenPath, token, { encoding: "utf8", mode: 0o600 });
  return token;
}

let mainWindow = null;
let backendProcess = null;
let backendStartedByApp = false;
let backendRecoveryTimer = null;
let backendRecoveryInFlight = false;
let backendRecoveryAttempts = 0;
let bridgeProcess = null;
let bridgeSequence = 0;
const bridgePending = new Map();
let runtimeConfig = loadConfig();
const desktopAuthToken = loadOrCreateDesktopAuthToken();
let desktopOwnerSessionToken = "";
let appQuitting = false;
const BACKEND_RECOVERY_LIMIT = 3;
const BACKEND_RECOVERY_DELAY_MS = 700;
const RUNTIME_LOG_MAX_BYTES = 2 * 1024 * 1024;
const WINDOW_BOUNDS_SAVE_DELAY_MS = 350;
let windowBoundsSaveTimer = null;
let pendingWindowBounds = null;

function readJsonConfig(configPath) {
  try {
    const payload = JSON.parse(fs.readFileSync(configPath, "utf8").replace(/^\uFEFF/, ""));
    return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  } catch (_error) {
    return {};
  }
}

function workspaceLocatorPaths() {
  const candidates = [];
  if (process.resourcesPath) {
    candidates.push(path.join(process.resourcesPath, WORKSPACE_LOCATOR_NAME));
  }
  const portableDir = String(process.env.PORTABLE_EXECUTABLE_DIR || "").trim();
  const portableFile = String(process.env.PORTABLE_EXECUTABLE_FILE || "").trim();
  if (portableDir) candidates.push(path.join(portableDir, WORKSPACE_LOCATOR_NAME));
  if (portableFile) candidates.push(path.join(path.dirname(portableFile), WORKSPACE_LOCATOR_NAME));
  candidates.push(path.join(path.dirname(process.execPath), WORKSPACE_LOCATOR_NAME));
  candidates.push(path.join(process.cwd(), WORKSPACE_LOCATOR_NAME));
  return [...new Set(candidates.map((candidate) => path.resolve(candidate)))];
}

function loadConfig() {
  const bundled = readJsonConfig(CONFIG_PATH);
  let locator = {};
  for (const candidate of workspaceLocatorPaths()) {
    locator = readJsonConfig(candidate);
    if (Object.keys(locator).length) break;
  }
  const user = readJsonConfig(USER_CONFIG_PATH);
  const merged = { ...DEFAULT_CONFIG, ...bundled, ...locator, ...user };
  if (!String(user.project_root || "").trim() && String(locator.project_root || "").trim()) {
    merged.project_root = locator.project_root;
  }
  return merged;
}

function backendBaseUrl() {
  return `http://127.0.0.1:${Number(runtimeConfig.backend_port) || 8767}`;
}

function workspaceRoot() {
  const configured = String(process.env.TEELAB_AGENT_ROOT || runtimeConfig.project_root || "").trim();
  if (configured) return path.resolve(configured);
  if (app.isPackaged) return path.join(app.getPath("userData"), "workspace");
  return path.resolve(__dirname, "..");
}

function bundledRuntimeExecutable() {
  if (process.env.TONE_USE_SOURCE_RUNTIME === "1") return "";
  const candidates = [];
  if (process.resourcesPath) {
    candidates.push(path.join(process.resourcesPath, "t-one-runtime", "t-one-runtime.exe"));
  }
  candidates.push(path.join(__dirname, "build", "t-one-runtime.exe"));
  return candidates.find((candidate) => fs.existsSync(candidate)) || "";
}

function bundledWorkspaceTemplate() {
  if (!process.resourcesPath) return "";
  const candidate = path.join(process.resourcesPath, "t-one-runtime", "template");
  return fs.existsSync(candidate) ? candidate : "";
}

function copyMissingTree(source, target) {
  if (!fs.existsSync(source)) return;
  fs.mkdirSync(target, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const sourcePath = path.join(source, entry.name);
    const targetPath = path.join(target, entry.name);
    if (entry.isDirectory()) copyMissingTree(sourcePath, targetPath);
    else if (entry.isFile() && !fs.existsSync(targetPath)) fs.copyFileSync(sourcePath, targetPath);
  }
}

function ensureWorkspaceSeeded() {
  const root = workspaceRoot();
  const template = bundledWorkspaceTemplate();
  if (template) copyMissingTree(template, root);
  for (const directory of ["config", "projects", "tasks", "logs", "outputs"]) {
    fs.mkdirSync(path.join(root, directory), { recursive: true });
  }
}

function workspaceSignature() {
  return crypto.createHash("sha256").update(workspaceRoot().toLowerCase(), "utf8").digest("hex").slice(0, 16);
}

async function chooseLocalVideoFile() {
  const owner = mainWindow && !mainWindow.isDestroyed() ? mainWindow : undefined;
  const options = {
    title: "选择本地视频",
    properties: ["openFile"],
    filters: [
      { name: "视频文件", extensions: ["mp4", "mov", "mkv", "webm", "avi", "m4v"] }
    ]
  };
  const result = owner
    ? await dialog.showOpenDialog(owner, options)
    : await dialog.showOpenDialog(options);
  if (result.canceled || !Array.isArray(result.filePaths) || !result.filePaths[0]) {
    return { ok: false, error: "没有选择视频。" };
  }
  const selected = path.resolve(String(result.filePaths[0]));
  const allowed = new Set([".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"]);
  if (!allowed.has(path.extname(selected).toLowerCase())) {
    return { ok: false, error: "当前文件不是支持的视频格式。" };
  }
  return { ok: true, path: selected };
}

function runtimeLogPath() {
  return path.join(workspaceRoot(), "logs", "desktop-runtime.log");
}

function safeRuntimeMessage(error) {
  return String(error && error.message ? error.message : error || "")
    .replace(/(api[_ -]?key|token|password|secret)\s*[:=]\s*[^\s,;]+/gi, "$1=[redacted]")
    .slice(0, 500);
}

function safeRuntimeUrl(rawUrl) {
  try {
    const parsed = new URL(String(rawUrl || ""));
    if (parsed.protocol === "data:") return "data:[local-startup]";
    return `${parsed.protocol}//${parsed.host}${parsed.pathname}`.slice(0, 300);
  } catch (_error) {
    return safeRuntimeMessage(rawUrl).split(/[?#]/, 1)[0].slice(0, 300);
  }
}

function writeRuntimeLog(event, details = {}) {
  try {
    const logPath = runtimeLogPath();
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.appendFileSync(logPath, `${JSON.stringify({ time: new Date().toISOString(), event, ...details })}\n`, "utf8");
    const size = fs.statSync(logPath).size;
    if (size > RUNTIME_LOG_MAX_BYTES) {
      const content = fs.readFileSync(logPath);
      fs.writeFileSync(logPath, content.subarray(content.length - Math.floor(RUNTIME_LOG_MAX_BYTES / 2)));
    }
  } catch (_error) {
    // Runtime logging must never prevent the app from starting.
  }
}

async function backendStatus(port = Number(runtimeConfig.backend_port) || 8767) {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/health`, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) return null;
    return await response.json();
  } catch (_error) {
    return null;
  }
}

async function backendIsHealthy(port = Number(runtimeConfig.backend_port) || 8767) {
  const payload = await backendStatus(port);
  return backendStatusIsCompatible(payload, workspaceRoot(), workspaceSignature());
}

async function requestDesktopSession(port = Number(runtimeConfig.backend_port) || 8767) {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/api/desktop/session`, {
      method: "POST",
      headers: { "X-TeeLab-Desktop-Token": desktopAuthToken },
      signal: AbortSignal.timeout(1500)
    });
    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload.ok && payload.session_token) {
      desktopOwnerSessionToken = String(payload.session_token);
      return { ok: true, profileMissing: false };
    }
    return {
      ok: false,
      profileMissing: response.status === 409 && payload.code === "account_profile_missing"
    };
  } catch (_error) {
    return { ok: false, profileMissing: false };
  }
}

function portIsOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(value);
    };
    socket.setTimeout(300);
    socket.once("connect", () => finish(true));
    socket.once("timeout", () => finish(false));
    socket.once("error", () => finish(false));
  });
}

async function selectBackendPort() {
  const preferred = Number(runtimeConfig.backend_port) || 8767;
  for (let port = preferred; port < preferred + 50; port += 1) {
    if (await backendIsHealthy(port)) {
      const session = await requestDesktopSession(port);
      if (session.ok || session.profileMissing) return port;
      continue;
    }
    if (!(await portIsOpen(port))) return port;
  }
  throw new Error("没有找到可用的 TeeLab 本地服务端口。");
}

function pythonLaunchCandidates() {
  const configured = String(process.env.TEELAB_AGENT_PYTHON || runtimeConfig.python_executable || "").trim();
  const candidates = [];
  if (configured) candidates.push({ command: configured, args: [] });
  if (process.platform === "win32") candidates.push({ command: "py", args: ["-3"] });
  candidates.push({ command: "python", args: [] });
  return candidates;
}

function backendLaunchCandidates() {
  const root = workspaceRoot();
  const port = String(Number(runtimeConfig.backend_port) || 8767);
  const candidates = [];
  const bundled = bundledRuntimeExecutable();
  if (bundled) {
    candidates.push({ command: bundled, args: ["server", "--root", root, "--port", port], bundled: true });
  }
  const script = path.join(root, "scripts", "start_local_server_port.py");
  if (fs.existsSync(script)) {
    for (const candidate of pythonLaunchCandidates()) {
      candidates.push({
        command: candidate.command,
        args: [...candidate.args, script, port, "--root", root],
        bundled: false
      });
    }
  }
  return candidates;
}

function bridgeLaunchCandidates() {
  const root = workspaceRoot();
  const candidates = [];
  const bundled = bundledRuntimeExecutable();
  if (bundled) {
    candidates.push({ command: bundled, args: ["bridge", "--root", root], bundled: true });
  }
  const projectBridge = path.join(root, "desktop_app", "bridge.py");
  const bridgeScript = fs.existsSync(projectBridge) ? projectBridge : path.join(__dirname, "bridge.py");
  if (fs.existsSync(bridgeScript)) {
    for (const candidate of pythonLaunchCandidates()) {
      candidates.push({
        command: candidate.command,
        args: [...candidate.args, bridgeScript, "--root", root],
        bundled: false
      });
    }
  }
  return candidates;
}

async function waitForBackend(timeoutMs = 60000, child = null) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (child && child.__tOneSpawnError) throw child.__tOneSpawnError;
    if (child && child.exitCode !== null) {
      throw new Error(`Python 后端提前退出（exit=${child.exitCode}）`);
    }
    if (await backendIsHealthy()) return true;
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
  return false;
}

function spawnBackendWith(candidate) {
  const root = workspaceRoot();
  const child = spawn(candidate.command, candidate.args, {
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
      TEELAB_DESKTOP_AUTH_TOKEN: desktopAuthToken
    }
  });
  child.__tOneSpawnError = null;
  child.once("error", (error) => {
    child.__tOneSpawnError = error;
    writeRuntimeLog("backend_spawn_error", {
      command: path.basename(String(candidate.command || "")),
      error: safeRuntimeMessage(error)
    });
  });
  writeRuntimeLog("backend_spawn", { pid: child.pid || 0, port: Number(runtimeConfig.backend_port) || 0 });
  child.stdout.on("data", (chunk) => process.stdout.write(`[backend] ${chunk}`));
  child.stderr.on("data", (chunk) => {
    const message = safeRuntimeMessage(String(chunk || "").trim());
    if (message) writeRuntimeLog("backend_stderr", { message });
    process.stderr.write(`[backend] ${chunk}`);
  });
  child.on("exit", (code, signal) => {
    const wasCurrentBackend = backendProcess === child;
    if (wasCurrentBackend) {
      backendProcess = null;
      backendStartedByApp = false;
    }
    writeRuntimeLog("backend_exit", { code: code ?? null, signal: signal || "", unexpected: wasCurrentBackend && !appQuitting });
    if (wasCurrentBackend && !appQuitting) scheduleBackendRecovery();
  });
  return child;
}

async function ensureBackend() {
  runtimeConfig.backend_port = await selectBackendPort();
  if (await backendIsHealthy()) {
    const session = await requestDesktopSession();
    if (session.ok || session.profileMissing) return true;
  }
  let firstError = null;
  let lastError = null;
  const candidates = backendLaunchCandidates();
  if (!candidates.length) throw new Error("找不到 T One 内置运行时或可用的 Python 运行时。");
  for (const candidate of candidates) {
    try {
      backendProcess = spawnBackendWith(candidate);
      backendStartedByApp = true;
      if (await waitForBackend(60000, backendProcess)) {
        const session = await requestDesktopSession();
        if (session.ok || session.profileMissing) return true;
      }
      throw new Error("Python 后端未在 60 秒内通过健康检查。");
    } catch (error) {
      if (!firstError) firstError = error;
      lastError = error;
      stopBackend();
    }
  }
  throw firstError || lastError || new Error("本地 AI 服务启动失败");
}

async function installDesktopSessionCookie() {
  if (!desktopOwnerSessionToken || !mainWindow || mainWindow.isDestroyed()) return;
  await mainWindow.webContents.session.cookies.set({
    url: backendBaseUrl(),
    name: "acct_session",
    value: desktopOwnerSessionToken,
    path: "/",
    httpOnly: true,
    sameSite: "lax"
  });
}

async function refreshWindowAfterBackendRecovery() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  let targetPath = resolveStartupPath(runtimeConfig.start_path);
  try {
    const current = new URL(mainWindow.webContents.getURL());
    targetPath = resolveStartupPath(`${current.pathname}${current.search}${current.hash}`);
  } catch (_error) {
    // Fall back to the configured start page when the failed page has no URL.
  }
  await requestDesktopSession();
  await installDesktopSessionCookie();
  await mainWindow.loadURL(`${backendBaseUrl()}${targetPath.startsWith("/") ? targetPath : `/${targetPath}`}`);
}

function scheduleBackendRecovery() {
  if (appQuitting || backendRecoveryTimer || backendRecoveryInFlight) return;
  if (backendRecoveryAttempts >= BACKEND_RECOVERY_LIMIT) {
    writeRuntimeLog("backend_recovery_exhausted", { attempts: backendRecoveryAttempts });
    return;
  }
  const delay = BACKEND_RECOVERY_DELAY_MS * Math.pow(2, backendRecoveryAttempts);
  writeRuntimeLog("backend_recovery_scheduled", { attempt: backendRecoveryAttempts + 1, delay_ms: delay });
  backendRecoveryTimer = setTimeout(async () => {
    backendRecoveryTimer = null;
    backendRecoveryInFlight = true;
    backendRecoveryAttempts += 1;
    writeRuntimeLog("backend_recovery_started", { attempt: backendRecoveryAttempts });
    try {
      await ensureBackend();
      await refreshWindowAfterBackendRecovery();
      writeRuntimeLog("backend_recovery_success", { attempt: backendRecoveryAttempts, port: Number(runtimeConfig.backend_port) || 0 });
      backendRecoveryAttempts = 0;
    } catch (error) {
      writeRuntimeLog("backend_recovery_failed", { attempt: backendRecoveryAttempts, error: safeRuntimeMessage(error) });
    } finally {
      backendRecoveryInFlight = false;
    }
    if (backendRecoveryAttempts > 0) scheduleBackendRecovery();
  }, delay);
}

function rejectBridgePending(error) {
  for (const pending of bridgePending.values()) {
    clearTimeout(pending.timer);
    pending.reject(error);
  }
  bridgePending.clear();
}

function spawnBridgeWith(candidate) {
  const root = workspaceRoot();
  const pythonPath = [root, process.env.PYTHONPATH || ""].filter(Boolean).join(path.delimiter);
  const child = spawn(candidate.command, candidate.args, {
    cwd: root,
    windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
    env: {
      ...process.env,
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
      PYTHONPATH: pythonPath
    }
  });
  writeRuntimeLog("bridge_spawn", { pid: child.pid || 0 });

  const ready = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("本地执行桥启动超时")), 12000);
    const output = readline.createInterface({ input: child.stdout });
    output.on("line", (line) => {
      if (!line.startsWith(BRIDGE_PREFIX)) {
        if (line.trim()) process.stdout.write(`[bridge] ${line}\n`);
        return;
      }
      let payload;
      try {
        payload = JSON.parse(line.slice(BRIDGE_PREFIX.length));
      } catch (_error) {
        return;
      }
      if (payload.type === "ready") {
        clearTimeout(timer);
        resolve(true);
        return;
      }
      const pending = bridgePending.get(String(payload.id || ""));
      if (!pending) return;
      bridgePending.delete(String(payload.id || ""));
      clearTimeout(pending.timer);
      if (payload.ok) pending.resolve(payload.result);
      else pending.reject(new Error(payload.error || "本地执行失败"));
    });
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.once("exit", (code) => {
      clearTimeout(timer);
      if (bridgeProcess === child) bridgeProcess = null;
      const error = new Error(`本地执行桥已退出 (${code ?? "unknown"})`);
      writeRuntimeLog("bridge_exit", { code: code ?? null, unexpected: !appQuitting });
      reject(error);
      rejectBridgePending(error);
    });
  });

  child.stderr.on("data", (chunk) => {
    const message = safeRuntimeMessage(String(chunk || "").trim());
    if (message) writeRuntimeLog("bridge_stderr", { message });
    process.stderr.write(`[bridge] ${chunk}`);
  });
  return { child, ready };
}

async function ensureBridge() {
  if (bridgeProcess && !bridgeProcess.killed && bridgeProcess.exitCode === null) return true;
  let lastError = null;
  const candidates = bridgeLaunchCandidates();
  if (!candidates.length) throw new Error("找不到 T One 内置执行桥或可用的 Python 运行时。");
  for (const candidate of candidates) {
    let started = null;
    try {
      started = spawnBridgeWith(candidate);
      bridgeProcess = started.child;
      await started.ready;
      return true;
    } catch (error) {
      lastError = error;
      if (started && !started.child.killed) started.child.kill();
      if (bridgeProcess === started?.child) bridgeProcess = null;
    }
  }
  throw lastError || new Error("本地执行桥启动失败");
}

async function invokeBridge(method, args) {
  await ensureBridge();
  const id = `desktop-${Date.now()}-${++bridgeSequence}`;
  const timeoutMs = {
    run_cli_ai_roundtrip: 360000,
    run_multi_ai_collaboration: 420000,
  }[String(method || "")] || 120000;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      bridgePending.delete(id);
      reject(new Error("本机任务调用超时；任务记录不会丢失。"));
    }, timeoutMs);
    bridgePending.set(id, { resolve, reject, timer });
    bridgeProcess.stdin.write(`${JSON.stringify({ id, method, args: Array.isArray(args) ? args : [] })}\n`, "utf8", (error) => {
      if (!error) return;
      bridgePending.delete(id);
      clearTimeout(timer);
      reject(error);
    });
  });
}

function stopBridge() {
  const error = new Error("T-one 正在退出");
  rejectBridgePending(error);
  if (!bridgeProcess) return;
  try {
    bridgeProcess.kill();
  } catch (_error) {
    // Process may already have exited.
  }
  bridgeProcess = null;
}

function stopBackend() {
  if (!backendProcess || !backendStartedByApp) return;
  const child = backendProcess;
  backendProcess = null;
  backendStartedByApp = false;
  try {
    child.kill();
  } catch (_error) {
    // Process may already have exited.
  }
}

function restoreWindowBounds() {
  try {
    const statePath = path.join(app.getPath("userData"), "window-state.json");
    const state = JSON.parse(fs.readFileSync(statePath, "utf8"));
    if (state && state.width >= 900 && state.height >= 640) return state;
  } catch (_error) {
    // First launch uses defaults.
  }
  return { width: 1500, height: 920 };
}

function saveWindowBounds() {
  if (!mainWindow || mainWindow.isDestroyed() || mainWindow.isMaximized()) return;
  pendingWindowBounds = mainWindow.getBounds();
  if (windowBoundsSaveTimer) clearTimeout(windowBoundsSaveTimer);
  windowBoundsSaveTimer = setTimeout(() => {
    windowBoundsSaveTimer = null;
    persistPendingWindowBounds();
  }, WINDOW_BOUNDS_SAVE_DELAY_MS);
}

function persistPendingWindowBounds() {
  if (!pendingWindowBounds) return;
  const bounds = pendingWindowBounds;
  pendingWindowBounds = null;
  try {
    const statePath = path.join(app.getPath("userData"), "window-state.json");
    fs.writeFileSync(statePath, JSON.stringify(bounds, null, 2), "utf8");
  } catch (_error) {
    // Window persistence is optional.
  }
}

function flushWindowBoundsSave() {
  if (windowBoundsSaveTimer) clearTimeout(windowBoundsSaveTimer);
  windowBoundsSaveTimer = null;
  persistPendingWindowBounds();
}

function isLocalAppUrl(rawUrl) {
  try {
    const url = new URL(rawUrl);
    return url.origin === backendBaseUrl();
  } catch (_error) {
    return false;
  }
}

function injectDesktopSurface() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.insertCSS(`
    html.desktop-shell .topbar {
      padding-left: 92px !important;
      -webkit-app-region: drag;
      user-select: none;
    }
    html.desktop-shell .topbar button,
    html.desktop-shell .topbar a,
    html.desktop-shell .topbar input,
    html.desktop-shell .topbar select {
      -webkit-app-region: no-drag;
    }
  `);
  mainWindow.webContents.executeJavaScript(
    "document.documentElement.classList.add('desktop-shell'); document.body.dataset.desktopApp = 'true';",
    true
  );
}

function loadingWindowDocument() {
  return [
    "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">",
    "<title>T-one</title>",
    "<style>html,body{height:100%;margin:0;background:#f5f7f8;color:#111318;font-family:Segoe UI,Microsoft YaHei,sans-serif}",
    "body{display:grid;place-items:center}.startup{display:grid;gap:12px;text-align:center}.mark{width:36px;height:36px;margin:auto;border-radius:10px;background:#111318;color:#fff;display:grid;place-items:center;font-weight:700}.hint{color:#65717c;font-size:14px}</style>",
    "</head><body><main class=\"startup\" aria-live=\"polite\"><div class=\"mark\">T1</div><strong>T-one 正在启动本地工作区</strong><span class=\"hint\">不会连接或写入外部平台</span></main></body></html>"
  ].join("");
}

async function loadDesktopWorkspace() {
  if (!mainWindow || mainWindow.isDestroyed()) throw new Error("T-one 主窗口不可用");
  if (!desktopOwnerSessionToken) await requestDesktopSession();
  await installDesktopSessionCookie();

  const configuredStartPath = String(runtimeConfig.start_path || "");
  const startPath = resolveStartupPath(configuredStartPath);
  if (startPath !== configuredStartPath) {
    writeRuntimeLog("startup_path_migrated_to_home", {
      configured_path: configuredStartPath,
      resolved_path: startPath
    });
  }
  await mainWindow.loadURL(`${backendBaseUrl()}${startPath}`);
}

async function createWindow({ loadWorkspace = true } = {}) {
  const bounds = restoreWindowBounds();
  let rendererNavigationStartedAt = 0;
  let rendererUnresponsiveAt = 0;
  mainWindow = new BrowserWindow({
    ...bounds,
    minWidth: 900,
    minHeight: 640,
    show: false,
    backgroundColor: "#f5f7f8",
    title: "T-one",
    autoHideMenuBar: true,
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#ffffff",
      symbolColor: "#111318",
      height: 54
    },
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isLocalAppUrl(url)) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (isLocalAppUrl(url)) return;
    event.preventDefault();
    shell.openExternal(url);
  });
  mainWindow.webContents.on("console-message", (_event, details, legacyMessage, legacyLine, legacySourceId) => {
    const modernDetails = details && typeof details === "object" ? details : null;
    const levelValue = modernDetails ? modernDetails.level : details;
    const levelNames = ["verbose", "info", "warning", "error"];
    const level = typeof levelValue === "number"
      ? levelNames[levelValue] || "unknown"
      : String(levelValue || "unknown").toLowerCase();
    if (!new Set(["warning", "error"]).has(level)) return;
    const message = modernDetails ? modernDetails.message : legacyMessage;
    const lineNumber = modernDetails ? modernDetails.lineNumber : legacyLine;
    const sourceId = modernDetails ? modernDetails.sourceId : legacySourceId;
    writeRuntimeLog("renderer_console", {
      level,
      message: safeRuntimeMessage(message),
      line: Number(lineNumber) || 0,
      source: safeRuntimeUrl(sourceId)
    });
  });
  mainWindow.webContents.on("did-start-loading", () => {
    rendererNavigationStartedAt = Date.now();
  });
  mainWindow.webContents.on("did-finish-load", () => {
    injectDesktopSurface();
    writeRuntimeLog("renderer_navigation_complete", {
      duration_ms: rendererNavigationStartedAt ? Date.now() - rendererNavigationStartedAt : 0,
      url: safeRuntimeUrl(mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : "")
    });
    rendererNavigationStartedAt = 0;
  });
  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    if (isMainFrame === false) return;
    writeRuntimeLog("renderer_load_failed", {
      error_code: Number(errorCode) || 0,
      error: safeRuntimeMessage(errorDescription),
      url: safeRuntimeUrl(validatedURL),
      duration_ms: rendererNavigationStartedAt ? Date.now() - rendererNavigationStartedAt : 0
    });
    rendererNavigationStartedAt = 0;
  });
  mainWindow.webContents.on("preload-error", (_event, preloadPath, error) => {
    writeRuntimeLog("renderer_preload_error", {
      preload: path.basename(String(preloadPath || "")),
      error: safeRuntimeMessage(error)
    });
  });
  mainWindow.on("unresponsive", () => {
    rendererUnresponsiveAt = Date.now();
    writeRuntimeLog("renderer_unresponsive", {
      url: safeRuntimeUrl(mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : "")
    });
  });
  mainWindow.on("responsive", () => {
    writeRuntimeLog("renderer_responsive", {
      unresponsive_ms: rendererUnresponsiveAt ? Date.now() - rendererUnresponsiveAt : 0,
      url: safeRuntimeUrl(mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : "")
    });
    rendererUnresponsiveAt = 0;
  });
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    writeRuntimeLog("renderer_process_gone", {
      reason: String(details && details.reason ? details.reason : "unknown"),
      exit_code: Number(details && details.exitCode) || 0,
      url: safeRuntimeUrl(mainWindow && !mainWindow.isDestroyed() ? mainWindow.webContents.getURL() : "")
    });
  });
  mainWindow.on("resize", saveWindowBounds);
  mainWindow.on("move", saveWindowBounds);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  if (loadWorkspace) await loadDesktopWorkspace();
  else await mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(loadingWindowDocument())}`);
  mainWindow.show();
  writeRuntimeLog("window_shown", { surface: loadWorkspace ? "workspace" : "local_startup" });
}

ipcMain.handle("desktop:get-runtime", () => ({
  desktop: true,
  appVersion: app.getVersion(),
  backendUrl: backendBaseUrl(),
  projectRoot: workspaceRoot()
}));

ipcMain.handle("desktop:api", async (event, method, args) => {
  const sourceUrl = String(event.senderFrame && event.senderFrame.url ? event.senderFrame.url : "");
  if (!isLocalAppUrl(sourceUrl)) throw new Error("拒绝非本地页面调用执行桥。");
  if (String(method || "") === "choose_video_file") return chooseLocalVideoFile();
  return invokeBridge(String(method || ""), Array.isArray(args) ? args : []);
});

ipcMain.handle("desktop:restart-backend", async () => {
  stopBackend();
  const ok = await ensureBackend();
  if (ok && mainWindow) await mainWindow.reload();
  return { ok };
});

ipcMain.handle("desktop:open-external", async (_event, rawUrl) => {
  const url = String(rawUrl || "");
  if (!/^https?:\/\//i.test(url)) return { ok: false };
  await shell.openExternal(url);
  return { ok: true };
});

const allowParallelE2E = process.env.TONE_E2E_ALLOW_PARALLEL === "1";
const gotLock = allowParallelE2E || app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });

  app.whenReady().then(async () => {
    try {
      ensureWorkspaceSeeded();
      await createWindow({ loadWorkspace: false });
      await ensureBackend();
      await ensureBridge();
      await loadDesktopWorkspace();
      writeRuntimeLog("app_ready", {
        app_version: app.getVersion(),
        backend_port: Number(runtimeConfig.backend_port) || 0,
        workspace_signature: workspaceSignature(),
        backend_source_signature: computeBackendSourceSignature(workspaceRoot())
      });
    } catch (error) {
      writeRuntimeLog("app_start_failed", { error: safeRuntimeMessage(error) });
      dialog.showErrorBox("T-one 启动失败", String(error && error.message ? error.message : error));
      app.quit();
    }
  });
}

app.on("before-quit", () => {
  appQuitting = true;
  if (backendRecoveryTimer) clearTimeout(backendRecoveryTimer);
  backendRecoveryTimer = null;
  flushWindowBoundsSave();
  writeRuntimeLog("app_quit");
  stopBridge();
  stopBackend();
});
app.on("child-process-gone", (_event, details) => {
  writeRuntimeLog("child_process_gone", {
    type: String(details && details.type ? details.type : "unknown"),
    reason: String(details && details.reason ? details.reason : "unknown"),
    name: String(details && details.name ? details.name : "").slice(0, 120),
    exit_code: Number(details && details.exitCode) || 0
  });
});
app.on("window-all-closed", () => app.quit());

if (process.env.TONE_DESKTOP_BOUNDS_TEST === "1") {
  module.exports.__windowBoundsTest = {
    createWindow,
    delayMs: WINDOW_BOUNDS_SAVE_DELAY_MS,
    flushWindowBoundsSave,
  };
}
