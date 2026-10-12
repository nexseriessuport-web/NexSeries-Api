const DEFAULT_TIMEOUT_MS = 10_000;

export function makeProvider({ id, baseEnv, searchPathEnv }) {
  const supportedOperations = ["search"];

  function config() {
    const base = process.env[baseEnv]?.trim();
    const path = process.env[searchPathEnv]?.trim();
    if (!base || !path) return null;

    let parsed;
    try { parsed = new URL(base); } catch { return null; }
    if (!["https:", "http:"].includes(parsed.protocol)) return null;

    // Require an absolute path template; do not accept a full arbitrary URL as a path.
    if (!path.startsWith("/") || path.startsWith("//")) return null;
    return { base: parsed, path };
  }

  async function search(query) {
    const cfg = config();
    if (!cfg) throw new Error("Provider is not configured");

    const url = new URL(cfg.path, cfg.base);
    url.searchParams.set("q", query);

    const timeoutMs = Math.max(1000, Math.min(
      Number(process.env.UPSTREAM_TIMEOUT_MS || DEFAULT_TIMEOUT_MS), 30000
    ));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        method: "GET",
        headers: { "accept": "application/json", "user-agent": "NexSeries-API-Workspace/1.0" },
        signal: controller.signal,
        redirect: "error"
      });
      if (!response.ok) {
        const error = new Error(`Upstream returned HTTP ${response.status}`);
        error.code = "UPSTREAM_HTTP_ERROR";
        throw error;
      }
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error("Upstream did not return JSON");
      }
      return await response.json();
    } catch (error) {
      if (error?.name === "AbortError") {
        const timeout = new Error("Upstream timed out");
        timeout.code = "UPSTREAM_TIMEOUT";
        throw timeout;
      }
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    id,
    supportedOperations,
    isConfigured: () => Boolean(config()),
    search
  };
}
