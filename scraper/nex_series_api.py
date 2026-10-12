from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import HTMLResponse
from bs4 import BeautifulSoup
import requests
import sqlite3
import datetime
import os
from urllib.parse import urlparse, urljoin

app = FastAPI(title="Nex Series API Scraper", version="10.1")
DB_FILE = os.getenv("DB_FILE", "nex_series.db")
TIMEOUT = 15
ALLOWED_HOSTS = {
    "animekai.be", "www.animekai.be",
    "anikoto.wtf", "www.anikoto.wtf",
    "hianime.to", "www.hianime.to",
    "anivault.co", "www.anivault.co",
}
HEADERS = {
    "User-Agent": "NexSeriesApi/10.1 (+public anime metadata scraper)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8",
}

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
            poster TEXT DEFAULT '', last_episode TEXT DEFAULT 'Ep 1',
            UNIQUE(platform, title))""")
init_db()

def validate_provider_url(url: str, platform: str):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail="URL must be HTTPS on a supported provider host.")
    expected = {
        "animekai": {"animekai.be", "www.animekai.be"},
        "anikoto": {"anikoto.wtf", "www.anikoto.wtf"},
        "hianime": {"hianime.to", "www.hianime.to"},
        "anivault": {"anivault.co", "www.anivault.co"},
    }.get(platform)
    if not expected or host not in expected:
        raise HTTPException(status_code=400, detail="URL host does not match the selected provider.")
    return url

def fetch(url, params=None):
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise HTTPException(status_code=502, detail="Provider redirected the request; open the provider site directly.")
        response.raise_for_status()
        return response
    except HTTPException:
        raise
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Provider request failed or timed out.")

def anilist(query, sort="POPULARITY_DESC", status=None, fmt=None, genre=None):
    filters = ["type: ANIME", "sort: " + sort]
    variables = {}
    if query:
        filters.append("search: $search")
        variables["search"] = query
    if status:
        filters.append("status: " + status)
    if fmt:
        filters.append("format: " + fmt)
    if genre:
        filters.append("genre: $genre")
        variables["genre"] = genre
    defs = []
    if query: defs.append("$search: String")
    if genre: defs.append("$genre: String")
    definition = "(" + ", ".join(defs) + ")" if defs else ""
    gql = "query " + definition + " { Page(perPage: 15) { media(" + ", ".join(filters) + ") { id title { english romaji } episodes format status coverImage { large } } } }"
    try:
        resp = requests.post("https://graphql.anilist.co", json={"query": gql, "variables": variables},
                             headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("errors"): raise ValueError("AniList returned an error")
        return [{"title": m.get("title", {}).get("english") or m.get("title", {}).get("romaji") or "Untitled",
                 "url": f"https://anivault.co/anime/{m['id']}", "id": m["id"],
                 "episodes": m.get("episodes"), "format": m.get("format"),
                 "status": m.get("status"), "poster": (m.get("coverImage") or {}).get("large")}
                for m in payload.get("data", {}).get("Page", {}).get("media", [])]
    except Exception:
        raise HTTPException(status_code=502, detail="AniList metadata service is temporarily unavailable.")

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return HTML

@app.get("/api/health")
def health():
    return {"status":"online","scraper":"Nex Series API Scraper","version":"10.1"}

@app.get("/api/search")
def search(platform: str = Query(...), q: str = Query(..., min_length=1, max_length=160)):
    platform = platform.lower()
    if platform == "anivault":
        return {"platform":platform,"query":q,"source":"AniList metadata","results":anilist(q)}
    roots = {"animekai":("https://animekai.be/","?s"),"anikoto":("https://anikoto.wtf/search","keyword"),
             "hianime":("https://hianime.to/search","keyword")}
    if platform not in roots: raise HTTPException(status_code=400, detail="Unsupported platform.")
    root, param = roots[platform]
    resp = fetch(root, params={"s" if param == "?s" else param:q})
    soup = BeautifulSoup(resp.text, "html.parser")
    selectors = {"animekai":"article, .post-item, .bs-item","anikoto":".flw-item, .film-detail, .item","hianime":".flw-item, .film-detail"}
    results, seen = [], set()
    for item in soup.select(selectors[platform]):
        link = item.select_one("a[href]")
        if not link: continue
        href = urljoin(root, link.get("href", ""))
        title = (link.get("title") or link.get_text(" ", strip=True)).strip()
        if title and href and href not in seen:
            seen.add(href); results.append({"title":title,"url":href})
    return {"platform":platform,"query":q,"results":results,"count":len(results)}

@app.get("/api/upcoming")
def upcoming():
    return {"category":"Upcoming Anime","results":anilist(None, status="NOT_YET_AIRED")}
@app.get("/api/top-airing")
def top_airing():
    return {"category":"Top Airing","results":anilist(None, status="RELEASING")}
@app.get("/api/most-popular")
def most_popular():
    return {"category":"Most Popular","results":anilist(None)}
@app.get("/api/movies")
def movies():
    return {"category":"Movies","results":anilist(None, fmt="MOVIE")}
@app.get("/api/schedule")
def schedule():
    return {"date":datetime.datetime.now(datetime.timezone.utc).date().isoformat(),"note":"Live release times are not configured; this endpoint does not invent a schedule.","schedule":[]}
@app.get("/api/genres")
def genres():
    return {"genres":["Action","Adventure","Comedy","Drama","Fantasy","Horror","Mystery","Romance","Sci-Fi","Slice of Life","Sports","Supernatural"]}
@app.get("/api/genre/{name}")
def by_genre(name: str):
    return {"genre":name,"results":anilist(None, genre=name.replace("-", " ").title())}
@app.get("/api/anime/details")
def details(platform: str = Query(...), url: str = Query(...)):
    url = validate_provider_url(url, platform.lower())
    soup = BeautifulSoup(fetch(url).text, "html.parser")
    title = soup.select_one("h1, .film-name, .title")
    return {"platform":platform,"url":url,"title":title.get_text(" ",strip=True) if title else "Anime Series"}
@app.get("/api/episodes")
def episodes(platform: str = Query(...), url: str = Query(...)):
    platform = platform.lower()
    url = validate_provider_url(url, platform)
    soup = BeautifulSoup(fetch(url).text, "html.parser")
    selectors = ".ss-list div[data-id], .ep-item a, ul.episodes-range li a, .eplister a"
    found, seen = [], set()
    for ep in soup.select(selectors):
        href = urljoin(url, ep.get("href") or "")
        label = ep.get_text(" ", strip=True) or ep.get("data-id") or str(len(found)+1)
        if href and href not in seen:
            seen.add(href); found.append({"episode":label,"url":href})
    return {"platform":platform,"total":len(found),"episodes":found,
            "note":None if found else "No episode links were detected; no fake episode list was generated."}
@app.get("/api/servers")
def servers(platform: str = Query(...), url: str = Query(...)):
    url = validate_provider_url(url, platform.lower())
    return {"platform":platform,"url":url,"servers":[{"name":"Provider page","url":url}],
            "note":"Only detected, real provider URLs are returned; server names are not fabricated."}
@app.get("/api/stream")
def stream(platform: str = Query(...), url: str = Query(...)):
    platform = platform.lower()
    url = validate_provider_url(url, platform)
    soup = BeautifulSoup(fetch(url).text, "html.parser")
    iframe = soup.select_one("iframe[src]")
    media = soup.select_one("video source[src], video[src]")
    source = media.get("src") if media else (iframe.get("src") if iframe else None)
    if not source:
        return {"platform":platform,"type":"unavailable","stream_url":None,
                "note":"No direct media or iframe URL was exposed in the page. DRM, ads, and access controls are not bypassed."}
    source = urljoin(url, source)
    parsed = urlparse(source)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=502, detail="Provider returned an unsupported media URL.")
    return {"platform":platform,"type":"hls" if ".m3u8" in parsed.path.lower() else "iframe",
            "stream_url":source,"ad_block_status":"not provided"}
@app.get("/api/watchlist")
def get_watchlist():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM watchlist ORDER BY id DESC").fetchall()
    return {"watchlist":[dict(row) for row in rows]}
@app.post("/api/watchlist")
def add_watchlist(data: dict = Body(...)):
    platform = str(data.get("platform","")).lower()
    title = str(data.get("title","")).strip()
    url = str(data.get("url","")).strip()
    if platform not in {"animekai","anikoto","hianime","anivault"} or not title or not url:
        raise HTTPException(status_code=400, detail="platform, title and url are required.")
    if platform != "anivault": validate_provider_url(url, platform)
    elif not url.startswith("https://anivault.co/"): raise HTTPException(status_code=400, detail="Invalid AniVault URL.")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""INSERT INTO watchlist(platform,title,url,poster,last_episode) VALUES(?,?,?,?,?)
        ON CONFLICT(platform,title) DO UPDATE SET url=excluded.url,poster=excluded.poster,last_episode=excluded.last_episode""",
        (platform,title,url,str(data.get("poster","")),str(data.get("last_episode","Ep 1"))))
    return {"status":"success","title":title}
HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nex Series API Scraper</title><style>
:root{color-scheme:dark;--bg:#09090b;--panel:#141419;--border:#303039;--accent:#a855f7;--muted:#a1a1aa}*{box-sizing:border-box}body{margin:0;padding:22px;font:15px system-ui;background:var(--bg);color:#f4f4f5}header,.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}header{justify-content:space-between;margin-bottom:18px}h1{font-size:22px;color:#c084fc;margin:0}button,input,select{border:1px solid var(--border);border-radius:8px;padding:10px 12px;background:#19191f;color:white}button{background:#9333ea;border:0;font-weight:700;cursor:pointer}.controls input{flex:1;min-width:180px}.grid{display:grid;grid-template-columns:minmax(280px,390px) 1fr;gap:16px;margin-top:16px}.panel{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px;min-height:160px}.item{padding:12px;border:1px solid var(--border);border-radius:8px;margin:8px 0;cursor:pointer}.item:hover{border-color:var(--accent)}pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#86efac}@media(max-width:750px){.grid{grid-template-columns:1fr}body{padding:12px}}</style></head><body><header><h1>⚡ Nex Series API Scraper</h1><span id="health">Checking API…</span></header><div class="controls"><select id="platform"><option>animekai</option><option>anikoto</option><option>hianime</option><option>anivault</option></select><input id="q" placeholder="Search anime title"><button onclick="search()">Search</button></div><div class="controls" style="margin-top:10px"><button onclick="quick('/api/upcoming')">Upcoming</button><button onclick="quick('/api/top-airing')">Top Airing</button><button onclick="quick('/api/most-popular')">Popular</button><button onclick="watchlist()">Watchlist</button><button onclick="apiInfo()">API JSON</button></div><div class="grid"><section class="panel"><h3 id="heading">Results</h3><div id="results">Search to begin.</div></section><section class="panel"><h3>Episodes / API output</h3><div id="episodes">Select an anime result.</div><pre id="output"></pre></section></div><script>
const $=id=>document.getElementById(id);let currentPlatform='animekai';
async function req(path,opts){const r=await fetch(path,opts);const d=await r.json();if(!r.ok)throw Error(d.detail||d.message||'Request failed');return d}
function show(id,data){$(id).innerHTML='';const arr=data.results||data.watchlist||[];if(!arr.length){$(id).textContent='No results returned.';return}arr.forEach(x=>{const el=document.createElement('div');el.className='item';el.textContent=x.title||x.name||x.episode||'Item';el.onclick=()=>{if(x.url)loadEpisodes(x.url,x.title||x.name||'')};$(id).appendChild(el)})}
async function search(){currentPlatform=$('platform').value;const q=$('q').value.trim();if(!q)return;try{const d=await req('/api/search?platform='+encodeURIComponent(currentPlatform)+'&q='+encodeURIComponent(q));show('results',d);$('output').textContent=JSON.stringify(d,null,2)}catch(e){$('results').textContent=e.message}}
async function quick(p){try{const d=await req(p);show('results',d);$('output').textContent=JSON.stringify(d,null,2)}catch(e){$('results').textContent=e.message}}
async function loadEpisodes(url,title){try{const d=await req('/api/episodes?platform='+encodeURIComponent(currentPlatform)+'&url='+encodeURIComponent(url));show('episodes',d);$('output').textContent=JSON.stringify(d,null,2);if(title&&currentPlatform!=='anivault')await req('/api/watchlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({platform:currentPlatform,title,url})})}catch(e){$('episodes').textContent=e.message}}
async function watchlist(){try{const d=await req('/api/watchlist');$('heading').textContent='My Watchlist';show('results',d);$('output').textContent=JSON.stringify(d,null,2)}catch(e){$('results').textContent=e.message}}
async function apiInfo(){try{$('output').textContent=JSON.stringify(await req('/openapi.json'),null,2)}catch(e){$('output').textContent=e.message}}
$('q').addEventListener('keydown',e=>{if(e.key==='Enter')search()});req('/api/health').then(d=>$('health').textContent=d.status+' · v'+d.version).catch(()=>$('health').textContent='API offline');
</script></body></html>"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("nex_series_api:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
