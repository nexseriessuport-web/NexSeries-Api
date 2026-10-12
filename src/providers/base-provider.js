const DEFAULT_TIMEOUT_MS = 10_000;

export function makeProvider({ id, baseEnv, searchPathEnv, episodesPathEnv, streamPathEnv }) {
  function configFor(pathEnv) {
    const base = process.env[baseEnv]?.trim();
    const path = process.env[pathEnv]?.trim();
    if (!base || !path) return null;

    let parsed;
    try { parsed = new URL(base); } catch { return null; }
    if (!["https:", "http:"].includes(parsed.protocol)) return null;
    if (!path.startsWith("/") || path.startsWith("//")) return null;
    return { base: parsed, path };
  }

  function supportedOperations() {
    return [
      ...(configFor(searchPathEnv) ? ["search"] : []),
      ...(configFor(episodesPathEnv) ? ["episodes"] : []),
      ...(configFor(streamPathEnv) ? ["stream"] : [])
    ];
  }

  async function request(pathEnv, values = {}) {
    const cfg = configFor(pathEnv);
    if (!cfg) {
      const error = new Error("Provider operation is not configured");
      error.code = "PROVIDER_NOT_CONFIGURED";
      throw error;
    }

    // IDs are encoded before being inserted into the configured path template.
    const path = cfg.path.replace(/\{(animeId|episodeId)\}/g, (_, key) =>
      encodeURIComponent(String(values[key] ?? ""))
    );
    if (/[{}]/.test(path)) throw new Error("Unsupported path template placeholder");
    const url = new URL(path, cfg.base);
    if (values.q !== undefined) url.searchParams.set("q", values.q);

    const timeoutMs = Math.max(1000, Math.min(
      Number(process.env.UPSTREAM_TIMEOUT_MS || DEFAULT_TIMEOUT_MS), 30000
    ));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        method: "GET",
        headers: { accept: "application/json", "user-agent": "NexSeries-API-Workspace/1.0" },
        signal: controller.signal,
        redirect: "error"
      });
      if (!response.ok) {
        const error = new Error(`Upstream returned HTTP ${response.status}`);
        error.code = "UPSTREAM_HTTP_ERROR";
        throw error;
      }
      if (!(response.headers.get("content-type") || "").includes("application/json")) {
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
    get supportedOperations() { return supportedOperations(); },
    isConfigured: () => Boolean(configFor(searchPathEnv)),
    isOperationConfigured: operation => Boolean(configFor(
      operation === "episodes" ? episodesPathEnv :
      operation === "stream" ? streamPathEnv : searchPathEnv
    )),
    search: query => request(searchPathEnv, { q: query }),
    episodes: animeId => request(episodesPathEnv, { animeId }),
    stream: episodeId => request(streamPathEnv, { episodeId })
  };
}
