from __future__ import annotations

import datetime as dt
import os
import sqlite3
from contextlib import contextmanager
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

APP_TITLE = "Nex Series API Scraper"
VERSION = "1.0.0"
DB_FILE = os.getenv("DB_FILE", "/data/nex_series.db" if os.path.isdir("/data") else "nex_series.db")
app = FastAPI(title=APP_TITLE, version=VERSION, description="Provider-based anime metadata and episode scraper API")

# Add providers here, or override their search URL with environment variables.
PROVIDERS: dict[str, dict[str, str]] = {
    "animekai": {"base": os.getenv("ANIMEKAI_BASE_URL", "https://animekai.to"), "search_path": os.getenv("ANIMEKAI_SEARCH_PATH", "/browser?keyword={query}"), "selectors": "article, .post-item, .bs-item, .flw-item"},
    "anikoto": {"base": os.getenv("ANIKOTO_BASE_URL", "https://anikoto.wtf"), "search_path": os.getenv("ANIKOTO_SEARCH_PATH", "/search?keyword={query}"), "selectors": ".flw-item, .film-detail, .item, article"},
    "hianime": {"base": os.getenv("HIANIME_BASE_URL", "https://hianime.to"), "search_path": os.getenv("HIANIME_SEARCH_PATH", "/search?keyword={query}"), "selectors": ".flw-item, .film-detail, article"},
    "anivault": {"base": os.getenv("ANIVAULT_BASE_URL", "https://anilist.co"), "search_path": "", "selectors": ""},
}

DASHBOARD = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nex Series API Scraper</title><style>
:root{color-scheme:dark;--bg:#09090b;--panel:#131318;--line:#292932;--accent:#a855f7;--muted:#a1a1aa}
*{box-sizing:border-box}body{margin:0;padding:20px;font:14px system-ui;background:var(--bg);color:#f4f4f5}header{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap}h1{font-size:22px;color:#c084fc;margin:0}.tabs,.controls{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}button,select,input{background:#1b1b22;border:1px solid var(--line);color:#fff;border-radius:8px;padding:10px}button{cursor:pointer}button.primary{background:var(--accent);border-color:var(--accent)}main{display:grid;grid-template-columns:minmax(280px,380px) minmax(0,1fr);gap:16px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;min-height:180px;overflow:auto}.results{max-height:65vh}.item{padding:11px;margin:7px 0;background:#1b1b22;border:1px solid transparent;border-radius:8px;cursor:pointer}.item:hover{border-color:var(--accent)}.muted{color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#86efac}.hidden{display:none}a{color:#c084fc}@media(max-width:760px){main{grid-template-columns:1fr}body{padding:12px}.results{max-height:none}}
</style></head><body><header><h1>⚡ Nex Series API Scraper</h1><span class="muted" id="health">Checking API…</span></header>
<div class="tabs"><button onclick="tab('search')">Search / Episodes</button><button onclick="quick('/api/upcoming')">Upcoming</button><button onclick="quick('/api/top-airing')">Top Airing</button><button onclick="quick('/api/most-popular')">Popular</button><button onclick="tab('watchlist');watchlist()">Watchlist</button><button onclick="tab('tester')">API Playground</button><a href="/docs" target="_blank"><button>Swagger Docs ↗</button></a></div>
<section id="search"><div class="controls"><select id="provider"><option>animekai</option><option>anikoto</option><option>hianime</option><option>anivault</option></select><input id="q" placeholder="Search anime title" style="flex:1;min-width:150px"><button class="primary" onclick="search()">Search</button></div><main><div class="panel results"><h3 id="leftTitle">Search results</h3><div id="results" class="muted">Search a title to begin.</div><hr><h3>Episodes</h3><div id="episodes" class="muted">Choose a result first.</div></div><div class="panel"><h3>Selected item / API response</h3><pre id="output">Ready.</pre><div id="player"></div></div></main></section>
<section id="watchlistView" class="hidden panel"><h2>Watchlist</h2><div id="watchitems"></div></section>
<section id="tester" class="hidden panel"><h2>API Playground</h2><div class="controls"><select id="endpoint"><option>/api/health</option><option>/api/providers</option><option>/api/search?platform=animekai&amp;q=Naruto</option><option>/api/upcoming</option><option>/api/top-airing</option><option>/api/most-popular</option><option>/api/movies</option><option>/api/schedule</option><option>/api/genres</option><option>/api/genre/action</option><option>/api/watchlist</option></select><button class="primary" onclick="testApi()">Send request</button></div><pre id="testout">Select a route.</pre></section>
<script>
let currentPlatform='animekai';
async function request(path,opts){const r=await fetch(path,opts);let d;try{d=await r.json()}catch{d={detail:await r.text()}}if(!r.ok)throw Error(d.detail||('HTTP '+r.status));return d}
function show(id){for(const x of ['search','watchlistView','tester'])document.getElementById(x).classList.toggle('hidden',x!==id)}
function tab(t){show(t==='watchlist'?'watchlistView':t==='tester'?'tester':'search')}
function out(v){document.getElementById('output').textContent=JSON.stringify(v,null,2)}
function addItem(container,title,click){const b=document.createElement('button');b.className='item';b.textContent=title;b.style.width='100%';b.style.textAlign='left';b.onclick=click;container.appendChild(b)}
async function search(){const q=document.getElementById('q').value.trim();currentPlatform=document.getElementById('provider').value;if(!q)return;const c=document.getElementById('results');c.textContent='Searching…';document.getElementById('episodes').textContent='Choose a result first.';try{const d=await request('/api/search?platform='+encodeURIComponent(currentPlatform)+'&q='+encodeURIComponent(q));c.replaceChildren();out(d);if(!d.results.length)c.textContent='No results. Provider may be unavailable or its page layout may have changed.';for(const x of d.results)addItem(c,x.title,()=>loadEpisodes(x))}catch(e){c.textContent=e.message}}
async function loadEpisodes(x){out(x);try{await request('/api/watchlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({platform:currentPlatform,title:x.title,url:x.url,poster:x.poster||''})});const d=await request('/api/episodes?platform='+encodeURIComponent(currentPlatform)+'&url='+encodeURIComponent(x.url));const c=document.getElementById('episodes');c.replaceChildren();if(!d.episodes.length)c.textContent='No episodes were detected for this title.';for(const ep of d.episodes)addItem(c,'Episode '+ep.episode,()=>play(ep.url));out(d)}catch(e){out({error:e.message})}}
async function play(url){try{const d=await request('/api/stream?platform='+encodeURIComponent(currentPlatform)+'&url='+encodeURIComponent(url));out(d);const p=document.getElementById('player');p.replaceChildren();if(d.type==='hls'||d.type==='video'){const v=document.createElement('video');v.controls=true;v.style.width='100%';v.src=d.stream_url;p.appendChild(v)}else{const a=document.createElement('a');a.href=d.stream_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Open provider player in a new tab';p.appendChild(a)}}catch(e){out({error:e.message})}}
async function quick(path){show('search');const c=document.getElementById('results');c.textContent='Loading…';try{const d=await request(path);c.replaceChildren();out(d);for(const x of (d.results||[]))addItem(c,x.title,()=>{currentPlatform='anivault';loadEpisodes(x)})}catch(e){c.textContent=e.message}}
async function watchlist(){const c=document.getElementById('watchitems');c.textContent='Loading…';try{const d=await request('/api/watchlist');c.replaceChildren();if(!d.watchlist.length)c.textContent='Your watchlist is empty.';for(const x of d.watchlist)addItem(c,'['+x.platform+'] '+x.title,()=>{currentPlatform=x.platform;show('search');loadEpisodes(x)})}catch(e){c.textContent=e.message}}
async function testApi(){const p=document.getElementById('endpoint').value;try{document.getElementById('testout').textContent=JSON.stringify(await request(p),null,2)}catch(e){document.getElementById('testout').textContent='Error: '+e.message}}
request('/api/health').then(d=>document.getElementById('health').textContent='● '+d.status+' · v'+d.version).catch(()=>document.getElementById('health').textContent='API unavailable');
</script></body></html>"""

@contextmanager
def db():
    conn = sqlite3.connect(DB_FILE, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL,
            title TEXT NOT NULL, url TEXT NOT NULL, poster TEXT DEFAULT '',
            last_episode TEXT DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(platform,title))""")

init_db()

def safe_provider_url(url: str, platform: str | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Only absolute HTTPS provider URLs are accepted.")
    host = parsed.hostname.lower()
    allowed = {urlparse(p["base"]).hostname.lower() for p in PROVIDERS.values() if p.get("base")}
    if platform in PROVIDERS:
        allowed.add(urlparse(PROVIDERS[platform]["base"]).hostname.lower())
    if host not in allowed and not any(host.endswith("." + h) for h in allowed):
        raise HTTPException(status_code=400, detail="URL host is not in the configured provider allowlist.")
    return url

def cf_get(url: str, params: dict[str, str] | None = None, platform: str | None = None) -> httpx.Response:
    safe_provider_url(url, platform)
    try:
        with httpx.Client(follow_redirects=True, timeout=15, headers={"User-Agent":"Mozilla/5.0 (compatible; NexSeriesApi/1.0)", "Accept":"text/html,application/xhtml+xml,application/json"}) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            # Revalidate redirect destination to reduce SSRF risk.
            safe_provider_url(str(response.url), platform)
            return response
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Provider request failed: {type(exc).__name__}") from exc

def anilist(query: str, variables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    gql = {"query": query, "variables": variables or {}}
    try:
        response = httpx.post("https://graphql.anilist.co", json=gql, timeout=15)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="AniList metadata request failed.") from exc
    if data.get("errors"):
        raise HTTPException(status_code=502, detail="AniList returned an API error.")
    return data.get("data", {}).get("Page", {}).get("media", [])

def anime_item(m: dict[str, Any]) -> dict[str, Any]:
    titles = m.get("title") or {}
    return {"title": titles.get("english") or titles.get("romaji") or "Untitled", "url": f"https://anilist.co/anime/{m['id']}", "poster": (m.get("coverImage") or {}).get("large", ""), "anilist_id": m["id"], "status": m.get("status")}

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return DASHBOARD

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status":"online", "scraper":APP_TITLE, "version":VERSION}

@app.get("/api/providers")
def providers() -> dict[str, Any]:
    return {"providers":[{"id":k,"base_url":v["base"],"mode":"AniList metadata" if k=="anivault" else "HTML search and episode parsing"} for k,v in PROVIDERS.items()]}

@app.get("/api/search")
def search(platform: str = Query(...), q: str = Query(..., min_length=1, max_length=120)) -> dict[str, Any]:
    platform = platform.lower()
    if platform not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider. Available: {', '.join(PROVIDERS)}")
    results: list[dict[str, Any]] = []
    if platform == "anivault":
        media = anilist("query ($search: String) { Page(perPage:10) { media(search:$search,type:ANIME,sort:SEARCH_MATCH) { id title { english romaji } coverImage { large } status } } }", {"search":q})
        results = [anime_item(m) for m in media]
    else:
        cfg = PROVIDERS[platform]
        path = cfg["search_path"].replace("{query}", quote(q, safe=""))
        base = cfg["base"].rstrip("/")
        target = urljoin(base + "/", path.lstrip("/"))
        # Search paths are fixed provider configuration; query parameters are URL-encoded.
        parsed = urlparse(target)
        params = {"keyword": q} if "keyword=" in path and "{query}" not in cfg["search_path"] else None
        if "{query}" not in cfg["search_path"] and "keyword=" in cfg["search_path"]:
            target = urljoin(base + "/", cfg["search_path"].split("?")[0].lstrip("/"))
        response = cf_get(target, params=params, platform=platform)
        soup = BeautifulSoup(response.text, "html.parser")
        seen: set[str] = set()
        for item in soup.select(cfg["selectors"]):
            link = item.select_one("a[href]")
            if not link:
                continue
            href = urljoin(base + "/", link.get("href", ""))
            if urlparse(href).hostname != urlparse(base).hostname:
                continue
            title = (link.get("title") or link.get_text(" ", strip=True) or item.get_text(" ", strip=True)).strip()
            if href and title and href not in seen:
                seen.add(href)
                image = item.select_one("img")
                results.append({"title":title[:250], "url":href, "poster":urljoin(base + "/", image.get("data-src") or image.get("src") or "") if image else ""})
                if len(results) >= 30:
                    break
    return {"platform":platform,"query":q,"count":len(results),"results":results}

def metadata_list(kind: str) -> dict[str, Any]:
    queries = {
        "upcoming": "query { Page(perPage:20) { media(status: NOT_YET_RELEASED, type:ANIME, sort:POPULARITY_DESC) { id title { english romaji } coverImage { large } status } } }",
        "top-airing": "query { Page(perPage:20) { media(status:RELEASING, type:ANIME, sort:POPULARITY_DESC) { id title { english romaji } coverImage { large } status } } }",
        "most-popular": "query { Page(perPage:20) { media(type:ANIME, sort:POPULARITY_DESC) { id title { english romaji } coverImage { large } status } } }",
        "movies": "query { Page(perPage:20) { media(format:MOVIE, type:ANIME, sort:POPULARITY_DESC) { id title { english romaji } coverImage { large } status } } }",
    }
    return {"category":kind,"source":"AniList metadata (not episode/stream data)","results":[anime_item(m) for m in anilist(queries[kind]) ]}

@app.get("/api/upcoming")
def upcoming() -> dict[str, Any]: return metadata_list("upcoming")
@app.get("/api/top-airing")
def top_airing() -> dict[str, Any]: return metadata_list("top-airing")
@app.get("/api/most-popular")
def most_popular() -> dict[str, Any]: return metadata_list("most-popular")
@app.get("/api/movies")
def movies() -> dict[str, Any]: return metadata_list("movies")

@app.get("/api/schedule")
def schedule() -> dict[str, Any]:
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    query = "query ($date: Int) { Page(perPage:50) { airingSchedules(airingAt_greater:$date, sort:TIME) { airingAt episode media { id title { english romaji } } } } }"
    try:
        r = httpx.post("https://graphql.anilist.co", json={"query":"query ($from:Int) { Page(perPage:30) { airingSchedules(airingAt_greater:$from, sort:TIME) { airingAt episode media { id title { english romaji } } } } }","variables":{"from":int(dt.datetime.now(dt.timezone.utc).timestamp())}}, timeout=15)
        r.raise_for_status()
        raw = r.json().get("data",{}).get("Page",{}).get("airingSchedules",[])
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="AniList schedule request failed.") from exc
    return {"date":today,"source":"AniList airing schedule","schedule":[{"time":dt.datetime.fromtimestamp(x["airingAt"],dt.timezone.utc).isoformat(),"title":(x.get("media",{}).get("title") or {}).get("english") or (x.get("media",{}).get("title") or {}).get("romaji") or "Unknown","episode":x.get("episode"),"url":f"https://anilist.co/anime/{x['media']['id']}"} for x in raw]}

@app.get("/api/genres")
def genres() -> dict[str, list[str]]:
    return {"genres":["Action","Adventure","Comedy","Drama","Fantasy","Horror","Mystery","Romance","Science Fiction","Slice of Life","Sports","Supernatural","Thriller","Music","Mecha"]}

@app.get("/api/genre/{name}")
def genre(name: str) -> dict[str, Any]:
    query = "query ($genre:String) { Page(perPage:20) { media(genre:$genre,type:ANIME,sort:POPULARITY_DESC) { id title { english romaji } coverImage { large } status } } }"
    return {"genre":name,"results":[anime_item(m) for m in anilist(query,{"genre":name.replace("-"," ").title()})]}

@app.get("/api/anime/details")
def details(platform: str = Query(...), url: str = Query(...)) -> dict[str, Any]:
    if platform.lower() == "anivault":
        match = __import__("re").search(r"/anime/(\d+)", url)
        if match:
            q = "query ($id:Int) { Page { media(id:$id,type:ANIME) { id title { english romaji } description status episodes coverImage { large } } } }"
            data = anilist(q, {"id":int(match.group(1))})
            if data:
                m = data[0]
                return {"platform":platform,"url":url,"title":(m["title"].get("english") or m["title"].get("romaji")),"description":m.get("description"),"status":m.get("status"),"episodes":m.get("episodes"),"poster":(m.get("coverImage") or {}).get("large")}
    target = safe_provider_url(url, platform.lower())
    response = cf_get(target, platform=platform.lower())
    soup = BeautifulSoup(response.text,"html.parser")
    title = soup.select_one("h1, .film-name, .title, .film-title")
    return {"platform":platform,"url":target,"title":title.get_text(" ",strip=True) if title else "Unknown title","status":"page fetched"}

@app.get("/api/episodes")
def episodes(platform: str = Query(...), url: str = Query(...)) -> dict[str, Any]:
    platform = platform.lower()
    if platform not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unknown provider.")
    if platform == "anivault":
        match = __import__("re").search(r"/anime/(\d+)", url)
        if match:
            q = "query ($id:Int) { Media(id:$id,type:ANIME) { episodes } }"
            try:
                r = httpx.post("https://graphql.anilist.co",json={"query":q,"variables":{"id":int(match.group(1))}},timeout=15)
                r.raise_for_status()
                count = r.json().get("data",{}).get("Media",{}).get("episodes")
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502,detail="AniList metadata request failed.") from exc
            return {"platform":platform,"total":0,"episodes":[],"metadata_episode_count":count,"note":"AniList does not provide provider episode URLs."}
        return {"platform":platform,"total":0,"episodes":[],"note":"AniList metadata pages do not contain playable episode URLs."}
    response = cf_get(url, platform=platform)
    soup = BeautifulSoup(response.text,"html.parser")
    found: list[dict[str,str]] = []
    selectors = ".ss-list [data-id], .ep-item a, ul.episodes-range li a, .eplister a, .episodes a, a[href*='episode']"
    seen: set[str] = set()
    for ep in soup.select(selectors):
        href = ep.get("href") or ""
        if not href and ep.get("data-id"):
            continue
        link = urljoin(url,href)
        if urlparse(link).hostname != urlparse(url).hostname or link in seen:
            continue
        label = ep.get_text(" ",strip=True) or ep.get("title") or ""
        match = __import__("re").search(r"(\d+(?:\.\d+)?)",label)
        if not match:
            continue
        seen.add(link)
        found.append({"episode":match.group(1),"url":link,"label":label[:120]})
    found.sort(key=lambda x:float(x["episode"]))
    return {"platform":platform,"total":len(found),"episodes":found,"note":None if found else "No episode links were found in the provider page. No placeholder episodes were generated."}

@app.get("/api/servers")
def servers(platform: str = Query(...), url: str = Query(...)) -> dict[str, Any]:
    safe_provider_url(url,platform.lower())
    return {"platform":platform,"servers":[{"name":"Provider page","url":url}],"note":"Only servers actually present on the supplied page are reported; no fake mirror servers are generated."}

@app.get("/api/stream")
def stream(platform: str = Query(...), url: str = Query(...)) -> dict[str, Any]:
    platform = platform.lower()
    if platform not in PROVIDERS:
        raise HTTPException(status_code=400,detail="Unknown provider.")
    response = cf_get(url,platform=platform)
    soup = BeautifulSoup(response.text,"html.parser")
    iframe = soup.select_one("iframe[src]")
    media = soup.select_one("video[src], video source[src]")
    raw = (media.get("src") if media else None) or (iframe.get("src") if iframe else None)
    if not raw:
        # A direct media URL is only accepted when the user supplied it and the host is allowlisted.
        if urlparse(url).path.lower().endswith((".m3u8",".mp4",".webm")):
            raw = url
        else:
            raise HTTPException(status_code=404,detail="No media URL was exposed by the provider page.")
    stream_url = urljoin(url,raw)
    if urlparse(stream_url).scheme != "https":
        raise HTTPException(status_code=400,detail="Non-HTTPS media URLs are not supported.")
    return {"platform":platform,"type":"hls" if ".m3u8" in urlparse(stream_url).path.lower() else "video" if urlparse(stream_url).path.lower().endswith((".mp4",".webm")) else "iframe","stream_url":stream_url,"note":"Playback depends on provider permissions, browser support, and the provider's embed policy."}

@app.get("/api/watchlist")
def get_watchlist() -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY id DESC").fetchall()
    return {"watchlist":[dict(row) for row in rows]}

@app.post("/api/watchlist")
def add_watchlist(data: dict[str, Any] = Body(...)) -> dict[str, Any]:
    platform = str(data.get("platform","")).lower()
    title = str(data.get("title","")).strip()
    url = str(data.get("url","")).strip()
    if platform not in PROVIDERS or not title or not url:
        raise HTTPException(status_code=422,detail="platform, title, and url are required; platform must be configured.")
    safe_provider_url(url,platform)
    poster = str(data.get("poster",""))[:2000]
    last_ep = str(data.get("last_episode",""))[:100]
    with db() as conn:
        conn.execute("""INSERT INTO watchlist(platform,title,url,poster,last_episode,updated_at)
            VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(platform,title) DO UPDATE SET url=excluded.url,poster=excluded.poster,last_episode=excluded.last_episode,updated_at=CURRENT_TIMESTAMP""",
            (platform,title[:250],url,poster,last_ep))
    return {"status":"success","platform":platform,"title":title}

@app.delete("/api/watchlist/{item_id}")
def delete_watchlist(item_id: int) -> dict[str, Any]:
    with db() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE id=?",(item_id,))
    if not cur.rowcount:
        raise HTTPException(status_code=404,detail="Watchlist item not found.")
    return {"status":"deleted","id":item_id}
