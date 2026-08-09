const path = require("node:path");
const { app, BrowserWindow } = require("electron");

function createWindow() {
  const window = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 900,
    minHeight: 620,
    title: "T One 中文社区版",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event, url) => {
    if (url !== window.webContents.getURL()) event.preventDefault();
  });
  const demoPath = app.isPackaged
    ? path.join(process.resourcesPath, "public-demo", "chat-first-workspace.html")
    : path.join(__dirname, "..", "demo", "chat-first-workspace.html");
  window.loadFile(demoPath);
}

app.whenReady().then(() => {
  app.setAppUserModelId("org.tone.community.desktop");
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
