import test from "node:test";
import assert from "node:assert/strict";
import app from "../src/server.js";

async function withServer(fn) {
  const server = app.listen(0, "127.0.0.1");
  await new Promise(resolve => server.once("listening", resolve));
  const address = server.address();
  try { await fn(`http://127.0.0.1:${address.port}`); }
  finally { await new Promise((resolve, reject) => server.close(err => err ? reject(err) : resolve())); }
}

const catalogPayload = { data: { Page: { media: [{
  id: 1,
  title: { english: "Naruto", romaji: "Naruto", native: "ナルト" },
  coverImage: { large: "https://example.test/naruto.jpg" },
  episodes: 220,
  siteUrl: "https://anilist.co/anime/20"
}] } } };

test("health route responds with ok", async () => withServer(async base => {
  const res = await fetch(`${base}/health`);
  assert.equal(res.status, 200);
  assert.equal((await res.json()).ok, true);
}));

test("provider list includes both adapters and operation status", async () => withServer(async base => {
  const res = await fetch(`${base}/api/providers`);
  const body = await res.json();
  assert.equal(res.status, 200);
  assert.deepEqual(body.providers.map(p => p.id).sort(), ["animekai", "anikoto"]);
  assert.ok(body.providers.every(p => Array.isArray(p.supportedOperations)));
}));

test("unknown provider returns 404", async () => withServer(async base => {
  const res = await fetch(`${base}/api/nope/search?q=test`);
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "unknown_provider");
}));

test("missing search query returns 400", async () => withServer(async base => {
  const res = await fetch(`${base}/api/anikoto/search`);
  assert.equal(res.status, 400);
  assert.equal((await res.json()).error, "invalid_query");
}));

test("oversized provider query returns 400", async () => withServer(async base => {
  const res = await fetch(`${base}/api/anikoto/search?q=${"x".repeat(161)}`);
  assert.equal(res.status, 400);
  assert.equal((await res.json()).error, "invalid_query");
}));

test("unconfigured provider returns clearly labeled catalog metadata", async t => {
  const names = ["ANIKOTO_API_BASE","ANIKOTO_SEARCH_PATH","ANIKOTO_EPISODES_PATH","ANIKOTO_STREAM_PATH"];
  const old = Object.fromEntries(names.map(k => [k, process.env[k]]));
  names.forEach(k => delete process.env[k]);
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
    for (const k of names) old[k] === undefined ? delete process.env[k] : process.env[k] = old[k];
  });
  globalThis.fetch = async (url, options) => {
    if (String(url) !== "https://graphql.anilist.co") return originalFetch(url, options);
    assert.equal(options.method, "POST");
    return new Response(JSON.stringify(catalogPayload), { status: 200, headers: { "content-type": "application/json" } });
  };
  await withServer(async base => {
    const res = await fetch(`${base}/api/anikoto/search?q=naruto`);
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.provider, "anikoto");
    assert.equal(body.configured, false);
    assert.equal(body.streamsAvailable, false);
    assert.equal(body.data[0].title.english, "Naruto");
  });
});

test("episode route validates IDs and reports unconfigured operation", async () => withServer(async base => {
  const missing = await fetch(`${base}/api/anikoto/episodes`);
  assert.equal(missing.status, 400);
  assert.equal((await missing.json()).error, "invalid_anime_id");
  const unavailable = await fetch(`${base}/api/anikoto/episodes?animeId=naruto`);
  assert.equal(unavailable.status, 503);
  assert.equal((await unavailable.json()).error, "operation_not_configured");
}));

test("stream route validates IDs and reports unconfigured operation", async () => withServer(async base => {
  const missing = await fetch(`${base}/api/anikoto/stream`);
  assert.equal(missing.status, 400);
  assert.equal((await missing.json()).error, "invalid_episode_id");
  const unavailable = await fetch(`${base}/api/anikoto/stream?episodeId=episode-1`);
  assert.equal(unavailable.status, 503);
  assert.equal((await unavailable.json()).error, "operation_not_configured");
}));

test("catalog route validates query before upstream request", async () => withServer(async base => {
  const res = await fetch(`${base}/api/catalog/search?q=`);
  assert.equal(res.status, 400);
  assert.equal((await res.json()).error, "invalid_query");
}));

test("unknown routes return JSON 404", async () => withServer(async base => {
  const res = await fetch(`${base}/api/not-a-route`);
  assert.equal(res.status, 404);
  assert.equal((await res.json()).error, "not_found");
}));
