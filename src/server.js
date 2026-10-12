import express from "express";
import helmet from "helmet";
import { providers } from "./providers/index.js";
import { createProviderRouter } from "./routes/provider-router.js";

const app = express();
app.disable("x-powered-by");
app.use(helmet());
app.use(express.json({ limit: "100kb" }));

app.get("/", (_req, res) => {
  res.json({
    name: "NexSeries API Workspace",
    status: "ok",
    docs: "/api",
    health: "/health"
  });
});

app.get("/health", (_req, res) => {
  res.status(200).json({ ok: true, service: "nexseries-api", timestamp: new Date().toISOString() });
});

app.get("/api", (_req, res) => {
  res.json({
    routes: [
      "GET /health",
      "GET /api/providers",
      "GET /api/:provider/search?q=title"
    ],
    note: "Search requires a verified provider adapter configuration. Unconfigured providers return 503."
  });
});

app.get("/api/providers", (_req, res) => {
  res.json({
    providers: Object.values(providers).map(p => ({
      id: p.id,
      configured: p.isConfigured(),
      supportedOperations: p.supportedOperations
    }))
  });
});

app.use("/api", createProviderRouter(providers));

app.use((req, res) => {
  res.status(404).json({ error: "not_found", message: `No route for ${req.method} ${req.path}` });
});

app.use((err, _req, res, _next) => {
  console.error("[api-error]", err?.message ?? err);
  res.status(500).json({ error: "internal_error", message: "An unexpected server error occurred." });
});

const port = Number(process.env.PORT || 3000);
if (process.env.NODE_ENV !== "test") {
  app.listen(port, "0.0.0.0", () => console.log(`NexSeries API listening on ${port}`));
}

export default app;
