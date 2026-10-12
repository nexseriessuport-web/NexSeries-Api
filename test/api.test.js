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

const catalogPayload = {
  data: {
    Page: {
      media: [{
        id: 1,
        title: { english: "Naruto", romaji: "Naruto", native: "ナルト" },
        coverImage: { large: "https://example.test/naruto.jpg" },
        episodes: 220,
        siteUrl: "https://anilist.co/anime/20"
      }]
    }
  }
};

test("health route responds with ok", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/health`);
    assert.equal(res.status, 200);
    assert.equal((await res.json()).ok, true);
  });
});

test("provider list includes both adapters and reports configuration", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/providers`);
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.deepEqual(body.providers.map(p => p.id).sort(), ["animekai", "anikoto"]);
    assert.ok(body.providers.every(p => typeof p.configured === "boolean"));
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

test("oversized provider query returns 400", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/anikoto/search?q=${"x".repeat(161)}`);
    assert.equal(res.status, 400);
    assert.equal((await res.json()).error, "invalid_query");
  });
});

test("unconfigured provider returns clearly labeled catalog metadata", async t => {
  const oldBase = process.env.ANIKOTO_API_BASE;
  const oldPath = process.env.ANIKOTO_SEARCH_PATH;
  delete process.env.ANIKOTO_API_BASE;
  delete process.env.ANIKOTO_SEARCH_PATH;
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
    if (oldBase === undefined) delete process.env.ANIKOTO_API_BASE;
    else process.env.ANIKOTO_API_BASE = oldBase;
    if (oldPath === undefined) delete process.env.ANIKOTO_SEARCH_PATH;
    else process.env.ANIKOTO_SEARCH_PATH = oldPath;
  });
  globalThis.fetch = async (url, options) => {
    assert.equal(String(url), "https://graphql.anilist.co");
    assert.equal(options.method, "POST");
    return new Response(JSON.stringify(catalogPayload), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
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

test("catalog route validates query before upstream request", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/catalog/search?q=`);
    assert.equal(res.status, 400);
    assert.equal((await res.json()).error, "invalid_query");
  });
});

test("unknown routes return JSON 404", async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/not-a-route`);
    assert.equal(res.status, 404);
    assert.equal((await res.json()).error, "not_found");
  });
});
