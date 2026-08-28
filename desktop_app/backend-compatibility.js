const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const DESKTOP_RUNTIME_VERSION = 4;
const BACKEND_SOURCE_FILES = [
  "ai_ecommerce_director/company_workspace.py",
  "ai_ecommerce_director/desktop_workspace.py",
  "ai_ecommerce_director/floating_ai_widget.py",
  "ai_ecommerce_director/server.py"
];

function computeBackendSourceSignature(root) {
  const digest = crypto.createHash("sha256");
  for (const relativePath of [...BACKEND_SOURCE_FILES].sort()) {
    const normalizedPath = relativePath.replace(/\\/g, "/");
    digest.update(normalizedPath, "utf8");
    digest.update(Buffer.from([0]));
    try {
      digest.update(fs.readFileSync(path.join(root, relativePath)));
    } catch (_error) {
      digest.update("<missing>", "utf8");
    }
    digest.update(Buffer.from([0]));
  }
  return digest.digest("hex").slice(0, 24);
}

function backendStatusIsCompatible(payload, root, expectedWorkspaceSignature) {
  return Boolean(
    payload &&
    payload.ok &&
    Number(payload.desktop_runtime_version || 0) === DESKTOP_RUNTIME_VERSION &&
    payload.workspace_signature === expectedWorkspaceSignature &&
    payload.backend_source_signature === computeBackendSourceSignature(root)
  );
}

module.exports = {
  BACKEND_SOURCE_FILES,
  DESKTOP_RUNTIME_VERSION,
  backendStatusIsCompatible,
  computeBackendSourceSignature
};
