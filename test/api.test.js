import test from "node:test";
import assert from "node:assert/strict";
import app from "../src/server.js";

async function withServer(fn) {
  const server = app.listen(0, "127.0.0.1");
  await new Promise(resolve => server.once("listening", resolve));
  const address = server.address();
  try {
    await fn(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise((resolve, reject) => server.close(err => err ? reject(err) : resolve()));
  }
}

test("health route responds with ok", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/health`);
    assert.equal(res.status, 200);
    assert.equal((await res.json()).ok, true);
  });
});

test("provider list includes both adapters", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/providers`);
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.deepEqual(body.providers.map(p => p.id).sort(), ["animekai", "anikoto"]);
  });
});

test("unknown provider returns 404", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/nope/search?q=test`);
    assert.equal(res.status, 404);
    assert.equal((await res.json()).error, "unknown_provider");
  });
});

test("missing search query returns 400", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/anikoto/search`);
    assert.equal(res.status, 400);
    assert.equal((await res.json()).error, "invalid_query");
  });
});

test("unconfigured provider returns 503 instead of pretending to work", async () => {
  delete process.env.ANIKOTO_API_BASE;
  delete process.env.ANIKOTO_SEARCH_PATH;
  await withServer(async base => {
    const res = await fetch(`${base}/api/anikoto/search?q=sample`);
    assert.equal(res.status, 503);
    assert.equal((await res.json()).error, "provider_not_configured");
  });
});
