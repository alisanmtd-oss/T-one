const fs = require("fs");
const path = require("path");

const desktopDir = __dirname;
const configPath = path.join(desktopDir, "app-config.json");
const outputPath = path.join(desktopDir, "build", "teelab-agent-root.json");

function prepareAndVerifyBuildResources() {
  if (!fs.existsSync(configPath)) {
    throw new Error(`Desktop app config is missing: ${configPath}`);
  }
  const config = JSON.parse(fs.readFileSync(configPath, "utf8").replace(/^\uFEFF/, ""));
  const payload = {
    project_root: "",
    backend_port: Number(config.backend_port) || 8767,
    start_path: String(config.start_path || "/desktop?view=dashboard"),
    python_executable: "",
    runtime_mode: "bundled"
  };

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

  const required = [
    outputPath,
    path.join(desktopDir, "build", "t-one-runtime", "t-one-runtime.exe"),
    path.join(desktopDir, "build", "runtime-template", "config"),
    path.join(desktopDir, "T-One-CLI.cmd")
  ];
  const missing = required.filter((item) => !fs.existsSync(item));
  if (missing.length) {
    throw new Error(`Required installer resources are missing:\n${missing.join("\n")}`);
  }
  process.stdout.write(`Prepared and verified desktop build resources: ${outputPath}\n`);
}

module.exports = async function beforePack() {
  prepareAndVerifyBuildResources();
};

if (require.main === module) {
  prepareAndVerifyBuildResources();
}
