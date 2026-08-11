const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tone", {
  loadWorkspace: () => ipcRenderer.invoke("workspace:load"),
  createProject: (payload) => ipcRenderer.invoke("project:create", payload),
  createTask: (payload) => ipcRenderer.invoke("task:create", payload),
  saveMessages: (payload) => ipcRenderer.invoke("task:save-messages", payload),
  chooseFiles: (payload) => ipcRenderer.invoke("task:choose-files", payload),
  assignCapability: (payload) => ipcRenderer.invoke("capability:assign", payload),
  setTaskExecutor: (payload) => ipcRenderer.invoke("task:set-executor", payload),
  openProjectFolder: (payload) => ipcRenderer.invoke("project:open-folder", payload),
  saveConnection: (payload) => ipcRenderer.invoke("connection:save", payload),
  detectCli: (payload) => ipcRenderer.invoke("connection:detect-cli", payload),
  testMcp: (payload) => ipcRenderer.invoke("connection:test-mcp", payload),
  runCli: (payload) => ipcRenderer.invoke("task:run-cli", payload),
  removeConnection: (payload) => ipcRenderer.invoke("connection:remove", payload),
});
