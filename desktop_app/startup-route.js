const HOME_PATH = "/desktop?view=dashboard";

function resolveStartupPath(rawPath) {
  const candidate = String(rawPath || "").trim();
  if (!candidate) return HOME_PATH;

  let parsed;
  try {
    parsed = new URL(candidate, "http://127.0.0.1");
  } catch (_error) {
    return HOME_PATH;
  }

  if (parsed.origin !== "http://127.0.0.1" || parsed.pathname !== "/desktop") {
    return HOME_PATH;
  }

  const view = String(parsed.searchParams.get("view") || "").trim().toLowerCase();
  if (view === "settings" || (!parsed.search && !parsed.hash)) {
    return HOME_PATH;
  }

  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

module.exports = { HOME_PATH, resolveStartupPath };
