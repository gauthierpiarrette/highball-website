#!/usr/bin/env python3
"""
Build gethighball.com from hand-written content + the highball-db data repo.

Usage:  python3 build.py [--db ../highball-db] [--out dist] [--base https://gethighball.com]

Output:
  /                     landing page
  /database/            filterable compatibility database (curated + predictions)
  /games/<slug>/        one page per game
                          - curated entries (101): indexed, renderer matrix + freshness + provenance
                          - predictions (12k):     noindex,follow until a Highball-specific signal exists
  /docs/<slug>/         hand-written pages (install, troubleshooting, credits, anti-cheat, about-the-data)
  /sitemap.xml          indexable URLs only
  /robots.txt /CNAME

No dependencies. Python 3.9+.
"""
import argparse, datetime, glob, html, json, os, re, shutil, sys

# ---------------------------------------------------------------- data loading

STATUS = {
    "verified-local":    ("Verified", "good",
                          "Tested by Highball on real Apple Silicon hardware."),
    "reported-upstream": ("Reported upstream", "info",
                          "Named in upstream release notes as working or fixed; not yet verified by Highball."),
    "community":         ("Community", "warn",
                          "Community consensus (AppleGamingWiki, r/macgaming); unverified by Highball."),
    "blocked-anticheat": ("Blocked", "bad",
                          "Kernel anti-cheat. Structurally impossible under any compatibility layer."),
}
STATUS_ORDER = {"verified-local": 0, "reported-upstream": 1, "community": 2, "blocked-anticheat": 3}
RENDERERS = ["dxvk", "dxmt", "d3dmetal"]
RENDERER_LABEL = {"dxvk": "DXVK", "dxmt": "DXMT", "d3dmetal": "D3DMetal", "wined3d": "wined3d"}
PRED_LABEL = {"likely": ("Likely playable", "good"), "maybe": ("Maybe", "warn"),
              "unlikely": ("Unlikely", "bad"), "blocked": ("Blocked", "bad")}


def slugify(s):
    s = re.sub(r"[’'`]", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or "game"


def load(dbpath):
    d = {}
    d["games"] = [json.load(open(f)) for f in sorted(glob.glob(f"{dbpath}/db/games/*.json"))]
    d["games"].sort(key=lambda g: (STATUS_ORDER.get(g.get("status"), 9), g["title"].lower()))
    d["recipes"] = {}
    for f in glob.glob(f"{dbpath}/recipes/*/*.json"):
        try:
            r = json.load(open(f))
            d["recipes"][r["id"]] = r
        except Exception:
            pass
    d["reports"] = {}
    for f in glob.glob(f"{dbpath}/db/reports/*.jsonl"):
        slug = os.path.basename(f)[:-6]
        d["reports"][slug] = [json.loads(l) for l in open(f) if l.strip()]
    try:
        d["derived"] = json.load(open(f"{dbpath}/db/derived/derived.json"))
    except Exception:
        d["derived"] = {"games": {}}
    try:
        d["anticheat"] = json.load(open(f"{dbpath}/db/anticheat.json"))
    except Exception:
        d["anticheat"] = {"games": {}}
    return d


# ---------------------------------------------------------------- layout

def layout(*, title, desc, path, body, base, noindex=False, og_image=None, jsonld=None,
           extra_head="", wide=False):
    """Wrap a body fragment in the site chrome. `path` is the absolute site path with trailing slash."""
    url = base.rstrip("/") + path
    og = og_image or f"{base.rstrip('/')}/static/og.png"
    nav = [("/database/", "Database", False), ("/vs/", "Compare", False),
           ("/docs/anti-cheat/", "Anti-cheat", True), ("/docs/install/", "Install", True),
           ("/docs/credits/", "Credits", True)]
    navhtml = "".join(
        '<a href="%s"%s%s>%s</a>' % (
            h,
            ' class="hide-s"' if s else "",
            ' aria-current="page"' if path == h else "",
            html.escape(t))
        for h, t, s in nav)
    if jsonld:
        graph = jsonld if isinstance(jsonld, list) else [jsonld]
        ld = "".join(f'<script type="application/ld+json">{json.dumps(o)}</script>' for o in graph)
    else:
        ld = ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
{'<meta name="robots" content="noindex,follow">' if noindex else ''}
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/static/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/static/favicon-16.png">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<meta name="theme-color" content="#16110A">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og}">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/static/style.css">
{extra_head}{ld}
</head>
<body>
<div class="topbar"><div class="wrap {'wrap-wide' if wide else ''} row">
  <a class="brand" href="/"><img src="/static/logo-128.png" alt="">Highball</a>
  <nav>{navhtml}</nav>
  <a class="dl" href="https://github.com/gauthierpiarrette/highball/releases/latest/download/Highball.dmg">Download</a>
</div></div>
{body}
<footer>
  <div class="foot-links">
    <a href="/database/">Compatibility database</a>
    <a href="/docs/credits/">Credits</a>
    <a href="/docs/troubleshooting/">Troubleshooting</a>
    <a href="https://github.com/gauthierpiarrette/highball">GitHub</a>
    <a href="https://github.com/gauthierpiarrette/highball/discussions">Discussions</a>
    <a href="https://github.com/gauthierpiarrette/highball-db">Contribute data</a>
  </div>
  <p class="legal">Built on Wine, Gcenx's engine builds, DXVK, DXMT and Apple's Game Porting Toolkit —
  <a href="/docs/credits/">sponsor them first</a>.<br>
  Curated compatibility data is CC0. Prediction data is derived from
  <a href="https://www.protondb.com">ProtonDB</a> reports and is licensed
  <a href="https://opendatacommons.org/licenses/odbl/1-0/">ODbL 1.0</a>; anti-cheat data from
  <a href="https://areweanticheatyet.com">AreWeAntiCheatYet</a> (MIT).</p>
</footer>
</body>
</html>
"""


def write(out, path, content):
    """path like '/games/portal-2/' -> dist/games/portal-2/index.html"""
    rel = path.strip("/")
    d = os.path.join(out, rel) if rel else out
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w").write(content)


# ---------------------------------------------------------------- game pages

def steam_art(appid):
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg" if appid else None


def renderer_matrix(game, reports):
    """Honest matrix: what we know per renderer, and empty cells as open asks."""
    rec = (game.get("renderer") or "").lower()
    seen = {}
    for r in reports:
        rr = (r.get("renderer") or "").lower()
        if rr:
            seen.setdefault(rr, []).append(r)
    rows = []
    for r in RENDERERS:
        label = RENDERER_LABEL[r]
        if r == rec:
            n = len(seen.get(r, []))
            detail = (f"{n} report{'s' if n != 1 else ''}" if n else "from the curated entry")
            rows.append(f'<tr><td class="r">{label}</td><td><span class="pill good">Recommended</span></td>'
                        f'<td class="sub">{detail}</td></tr>')
        elif r in seen:
            n = len(seen[r])
            rows.append(f'<tr><td class="r">{label}</td><td><span class="pill info">Reported</span></td>'
                        f'<td class="sub">{n} report{"s" if n != 1 else ""}</td></tr>')
        else:
            rows.append(f'<tr><td class="r unknown">{label}</td><td><span class="pill warn">Untested</span></td>'
                        f'<td class="sub">no report yet — '
                        f'<a href="https://github.com/gauthierpiarrette/highball-db/issues/new?template=report.yml">'
                        f'send one</a></td></tr>')
    return ('<div class="tablewrap"><table class="matrix"><thead><tr><th>Renderer</th><th>Verdict</th>'
            '<th>Evidence</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def faq_entries(title, game, blocked, label, stamp, has_recipe):
    """Real questions people type, answered in one paragraph each."""
    def qa(q, a):
        return {"@type": "Question", "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a}}
    out = []
    if blocked:
        out.append(qa(f"Does {title} work on Mac?",
                      f"No. {title} uses kernel-level anti-cheat, which needs a Windows kernel driver. "
                      f"Compatibility layers such as Highball, CrossOver and Whisky run entirely in user space, "
                      f"so there is nothing for that driver to load into. No Mac app can run it, and this will "
                      f"not change with a future release. Cloud streaming is the only way to play it on a Mac."))
        out.append(qa(f"Can I play {title} on Mac with CrossOver or Parallels?",
                      "No. The same limit applies to every compatibility layer, and to virtual machines: "
                      "the anti-cheat driver cannot load. Streaming services run the real Windows build on a "
                      "remote machine, which is why they work."))
    else:
        rec = game.get("renderer")
        out.append(qa(f"Does {title} work on Mac?",
                      f"{title} runs on Apple Silicon through Highball, a free open-source compatibility layer. "
                      f"Status in the Highball database: {label}. {stamp}."))
        if rec:
            out.append(qa(f"Which renderer should I use for {title}?",
                          f"{RENDERER_LABEL.get(rec, rec)}. Highball can translate Direct3D through DXVK, DXMT or "
                          f"Apple's D3DMetal, and the right choice varies by game. For {title} the database "
                          f"records {RENDERER_LABEL.get(rec, rec)}, and Highball selects it automatically."))
        if has_recipe:
            out.append(qa(f"Is there a one-click setup for {title}?",
                          f"Yes. Highball ships a recipe for {title} that applies the tested renderer and any "
                          f"per-game fixes automatically. Open the game in your Library and apply it."))
    return out


def game_page(game, data, base):
    slug, title = game["id"], game["title"]
    status = game.get("status", "community")
    label, cls, meaning = STATUS[status]
    appid = game.get("steam_appid")
    reports = data["reports"].get(slug, [])
    recipe = data["recipes"].get(slug)
    ac = game.get("anticheat")
    blocked = status == "blocked-anticheat"
    last = game.get("lastVerified")

    # freshness stamp — the field competitors don't publish per renderer/engine
    engine = next((r.get("engine") for r in reversed(reports) if r.get("engine")), None)
    macos = next((r.get("macos") for r in reversed(reports) if r.get("macos")), None)
    if last:
        bits = [f"last confirmed {last}"]
        if engine: bits.append(f"engine {engine}")
        if macos: bits.append(f"macOS {macos}")
        stamp = " · ".join(bits)
    else:
        stamp = "not yet confirmed on a dated Highball run"

    if blocked:
        verdict = (f"<b>{html.escape(title)} cannot run on a Mac through Highball, CrossOver, Whisky, "
                   f"or any other compatibility layer.</b> Its anti-cheat loads a Windows kernel driver, "
                   f"and macOS will never load one. This is not a bug anyone can fix.")
    else:
        rec = game.get("renderer")
        verdict = (f"Runs on Apple Silicon through Highball"
                   + (f" with the <b>{RENDERER_LABEL.get(rec, rec)}</b> renderer" if rec else "")
                   + f". {html.escape(meaning)}")

    art = steam_art(appid)
    head = f"""<div class="wrap">
<p class="crumbs"><a href="/">Highball</a> › <a href="/database/">Database</a> › {html.escape(title)}</p>
<div class="gamehead">
  {f'<img class="art" src="{art}" alt="" loading="lazy" referrerpolicy="no-referrer">' if art else ''}
  <div class="meta">
    <span class="pill {cls}">{label}</span>
    <h1>{html.escape(title)} on Mac</h1>
    <p class="verdict">{verdict}</p>
    <div class="kv">
      <span class="stamp">{html.escape(stamp)}</span>
      {f'<span>Steam {appid}</span>' if appid else ''}
      {f'<span>{len(reports)} community report{"s" if len(reports)!=1 else ""}</span>' if reports else ''}
    </div>
  </div>
</div></div>"""

    body = [head, '<div class="wrap prose">']

    if blocked:
        names = ", ".join(ac["names"]) if ac and ac.get("names") else "kernel anti-cheat"
        body.append(f"""<div class="note bad"><b>Anti-cheat: {html.escape(names)}.</b>
        Don't spend the download. Kernel-level anti-cheat needs a Windows driver running in ring 0;
        a translation layer runs entirely in user space, so there is nothing to load it into.
        Anti-cheat vendors can enable Linux support through Proton, but that path does not extend to macOS.</div>
        <h2>What actually works instead</h2>
        <p>Cloud streaming runs the real Windows build on someone else's machine, so the anti-cheat is
        satisfied. <a href="https://www.nvidia.com/en-us/geforce-now/">GeForce NOW</a> has a native Mac app and
        <a href="/docs/game-pass/">Xbox Cloud Gaming runs in a browser</a>; both publish the games they carry.
        And before assuming you need any of this, check whether the game
        <a href="/docs/native-mac-games/">already has a native Mac build</a> — a native build beats translation
        every time.</p>""")
    else:
        body.append("<h2>Which renderer to use</h2>")
        body.append("<p>Highball can run each game through three different Direct3D translation layers. "
                    "This is what the database knows for this title — empty rows are open questions, "
                    "not failures.</p>")
        body.append(renderer_matrix(game, reports))
        body.append(f'<p class="sub" style="margin-top:.7rem">{html.escape(stamp)}. '
                    f'Verdicts are stamped with the engine build and macOS version they were seen on, '
                    f'because a result without a date is a rumour.</p>')

    if game.get("notes"):
        body.append("<h2>Notes</h2><p>" + html.escape(game["notes"]).replace("\n", "</p><p>") + "</p>")

    if recipe:
        body.append(f"""<h2>One-click setup</h2>
        <p>Highball ships a recipe for {html.escape(title)}: open the game in your Library and apply it.
        The recipe carries the tested renderer and any per-game fixes, so you don't have to reproduce them by hand.
        <a href="https://github.com/gauthierpiarrette/highball-db/blob/main/recipes/games/{html.escape(recipe['id'])}.json">Read the recipe</a>.</p>""")

    if ac and not blocked:
        names = ", ".join(ac.get("names", []))
        body.append(f"""<div class="note"><b>Anti-cheat present: {html.escape(names)}.</b>
        {html.escape(ac.get('note') or 'Single-player generally works; online modes may refuse to launch.')}
        See <a href="/docs/anti-cheat/">how anti-cheat works on Mac</a>.</div>""")

    if game.get("provenance"):
        body.append(f'<h2>Provenance</h2><p class="sub">{html.escape(game["provenance"])}</p>')

    if not blocked:
        body.append('<p class="sub">Before installing anything, it is worth checking whether the game '
                    '<a href="/docs/native-mac-games/">already ships a native Mac build</a>.</p>')

    body.append(f"""<h2>Contribute a result</h2>
    <p>This page is generated from an open database. If you have run {html.escape(title)} on Apple Silicon,
    working or not, a report takes a minute and fills in the empty rows above.
    <a href="https://github.com/gauthierpiarrette/highball-db/issues/new?template=report.yml">Send a report</a>,
    or read <a href="/docs/data/">how the data is put together</a>.</p>
    <p><a class="btn" href="https://github.com/gauthierpiarrette/highball/releases/latest/download/Highball.dmg">Download Highball</a></p>
    </div>""")

    B = base.rstrip("/")
    ld = [{"@context": "https://schema.org", "@type": "VideoGame", "name": title,
           "url": f"{B}/games/{slug}/", "gamePlatform": ["macOS", "Apple Silicon"]},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Highball", "item": B + "/"},
              {"@type": "ListItem", "position": 2, "name": "Compatibility database", "item": B + "/database/"},
              {"@type": "ListItem", "position": 3, "name": title}]},
          {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faq_entries(
              title, game, blocked, label, stamp, bool(recipe))}]
    if appid:
        ld[0]["sameAs"] = f"https://store.steampowered.com/app/{appid}/"

    # title: keep under ~60 chars so it isn't truncated in results
    page_title = f"{title} on Mac — Highball compatibility"
    if len(page_title) > 60:
        page_title = f"{title} on Mac"[:60] if len(f"{title} on Mac") <= 60 else f"{title[:52].rstrip()}… on Mac"

    if blocked:
        desc = (f"{title} cannot run on a Mac: kernel anti-cheat needs a Windows driver that no compatibility "
                f"layer can load. Here is why, and what to do instead.")
    else:
        r = RENDERER_LABEL.get(game.get("renderer"), "")
        desc = (f"{title} on Apple Silicon through Highball: {label.lower()}"
                + (f", best with the {r} renderer" if r else "")
                + f". Per-renderer verdicts, provenance and the date it was last confirmed.")
    desc = desc[:158]
    return layout(title=page_title, desc=desc,
                  path=f"/games/{slug}/", body="".join(body), base=base,
                  og_image=art, jsonld=ld)


def prediction_page(appid, rec, base, slug):
    title = rec["title"]
    pred = rec.get("macPrediction", "maybe")
    plabel, pcls = PRED_LABEL.get(pred, ("Unknown", "warn"))
    acs = rec.get("anticheat") or []
    art = steam_art(appid)
    body = f"""<div class="wrap">
<p class="crumbs"><a href="/">Highball</a> › <a href="/database/">Database</a> › {html.escape(title)}</p>
<div class="gamehead">
  {f'<img class="art" src="{art}" alt="" loading="lazy" referrerpolicy="no-referrer">' if art else ''}
  <div class="meta">
    <span class="pill {pcls}">{plabel} (prediction)</span>
    <h1>{html.escape(title)} on Mac</h1>
    <p class="verdict"><b>Nobody has reported this game running on Apple Silicon yet.</b>
    What follows is a prediction derived from Linux data, not a verdict.</p>
    <div class="kv"><span>Steam {appid}</span>
      <span>Proton tier: {html.escape(rec.get('protonTier','unknown'))}</span>
      <span>{rec.get('recentReports',0)} recent Linux reports</span>
      {f'<span>Anti-cheat: {html.escape(", ".join(acs))}</span>' if acs else ''}
    </div>
  </div>
</div></div>
<div class="wrap prose">
<div class="note"><b>How this prediction is made.</b> Recent
<a href="https://www.protondb.com">ProtonDB</a> verdicts for this game are crossed with
<a href="https://areweanticheatyet.com">anti-cheat</a> data. Proton describes Linux, and Linux is not macOS —
different graphics stack, different translation layers, different failure modes. Treat this as odds, not an answer.</div>
<h2>Turn this into a real verdict</h2>
<p>If you own {html.escape(title)}, running it once through Highball and sending the result is what turns this
page from a guess into data — with the renderer, engine build and macOS version recorded.
<a href="https://github.com/gauthierpiarrette/highball-db/issues/new?template=report.yml">Send a report</a>.</p>
<p><a class="btn" href="https://github.com/gauthierpiarrette/highball/releases/latest/download/Highball.dmg">Download Highball</a>
<a class="btn ghost" href="/database/">Browse verified games</a></p>
</div>"""
    return layout(title=f"{title} on Mac — prediction | Highball",
                  desc=f"{title} on Apple Silicon: no verified Mac result yet. Prediction from Linux/Proton data plus anti-cheat knowledge.",
                  path=f"/games/{slug}/", body=body, base=base, noindex=True, og_image=art)


# ---------------------------------------------------------------- index pages

def database_page(data, base, counts, derived_count):
    games = data["games"]

    def row(g):
        label, cls, _ = STATUS[g["status"]]
        r = g.get("renderer")
        rr = RENDERER_LABEL.get(r, r) if r else '<span class="unknown">—</span>'
        n = len(data["reports"].get(g["id"], []))
        last = g.get("lastVerified") or "—"
        return (f'<tr data-status="{g["status"]}" data-t="{html.escape(g["title"].lower())}">'
                f'<td class="t"><a href="/games/{g["id"]}/">{html.escape(g["title"])}</a></td>'
                f'<td><span class="pill {cls}">{label}</span></td>'
                f'<td class="mono">{rr}</td>'
                f'<td class="mono sub">{last}</td>'
                f'<td class="num">{n or "—"}</td></tr>')

    tiles = "".join(
        f'<button class="tile" data-f="{k}" aria-pressed="false"><b>{counts[k]}</b>'
        f'<span>{STATUS[k][0]}</span><i class="bar {STATUS[k][1]}"></i></button>' for k in STATUS)

    body = f"""<div class="wrap wrap-wide">
<section style="padding-bottom:1.5rem">
<h1 style="font-size:clamp(2rem,5vw,2.9rem);margin:.2rem 0 .6rem">Compatibility database</h1>
<p style="color:var(--ink2);max-width:46em">Which Windows games run on Apple Silicon, which renderer each one needs,
and when that was last confirmed. Every claim carries its provenance. Curated data is CC0 —
<a href="https://github.com/gauthierpiarrette/highball-db">take it</a>.</p>
</section>
<div class="tiles">{tiles}</div>
<div class="search"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
<input type="search" id="q" placeholder="Filter {len(games)} curated titles…" aria-label="Filter by title"></div>
<div class="tablewrap"><table>
<thead><tr><th>Game</th><th>Status</th><th>Renderer</th><th>Last confirmed</th><th class="num">Reports</th></tr></thead>
<tbody id="rows">{"".join(row(g) for g in games)}</tbody></table></div>
<p class="sub" id="empty" style="display:none;padding:1rem">No curated entry matches. It may still have a prediction below.</p>

<section>
<h2 style="font-size:1.4rem">Predictions</h2>
<p style="color:var(--ink2);max-width:46em">{derived_count:,} more Steam games carry a machine-derived
prediction: recent <a href="https://www.protondb.com">ProtonDB</a> verdicts crossed with
<a href="https://areweanticheatyet.com">anti-cheat</a> data. Proton describes Linux, so these are odds,
not verdicts — and they are deliberately kept out of search results until someone confirms one on a Mac.</p>
<div class="search"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
<input type="search" id="dq" placeholder="Search {derived_count:,} predictions…" aria-label="Search predictions"></div>
<div class="tablewrap" id="dwrap" style="display:none"><table>
<thead><tr><th>Game</th><th>Prediction</th><th>Proton</th><th class="num">Reports</th></tr></thead>
<tbody id="drows"></tbody></table></div>
<p class="sub" id="dhint" style="padding:.6rem 0">Type at least two characters.</p>
</section>
</div>
<script>
const rows=[...document.querySelectorAll('#rows tr')];let f=null,q='';
function apply(){{let n=0;rows.forEach(r=>{{const ok=(!f||r.dataset.status===f)&&(!q||r.dataset.t.includes(q));r.style.display=ok?'':'none';if(ok)n++;}});
document.getElementById('empty').style.display=n?'none':'block';}}
document.querySelector('.tiles').addEventListener('click',e=>{{const b=e.target.closest('.tile');if(!b)return;
const k=b.dataset.f;f=(f===k)?null:k;document.querySelectorAll('.tile').forEach(t=>t.setAttribute('aria-pressed',t.dataset.f===f));apply();}});
document.getElementById('q').addEventListener('input',e=>{{q=e.target.value.toLowerCase().trim();apply();}});
let D=null;const dq=document.getElementById('dq');
dq.addEventListener('input',async e=>{{const v=e.target.value.toLowerCase().trim();
const wrap=document.getElementById('dwrap'),hint=document.getElementById('dhint');
if(v.length<2){{wrap.style.display='none';hint.style.display='block';hint.textContent='Type at least two characters.';return;}}
if(!D){{hint.textContent='Loading predictions…';D=await (await fetch('/data/predictions.json')).json();}}
const hits=Object.entries(D).filter(([id,g])=>g.t.toLowerCase().includes(v)).slice(0,80);
document.getElementById('drows').innerHTML=hits.map(([id,g])=>
`<tr><td class="t"><a href="/games/${{g.s}}/">${{g.t.replace(/</g,'&lt;')}}</a></td><td><span class="pill ${{g.c}}">${{g.p}}</span></td><td class="mono">${{g.pt}}</td><td class="num">${{g.n}}</td></tr>`).join('');
wrap.style.display=hits.length?'':'none';hint.style.display=hits.length?'none':'block';
if(!hits.length)hint.textContent='No prediction for that title.';}});
</script>"""
    return layout(title="Mac game compatibility database — Highball",
                  desc=f"Which Windows games run on Apple Silicon: {counts['verified-local']} verified, "
                       f"{derived_count:,} predictions, per-renderer verdicts with dates. Open data, CC0.",
                  path="/database/", body=body, base=base, wide=True)


def landing_page(data, base, counts, derived_count):
    verified = [g for g in data["games"] if g["status"] == "verified-local"][:6]
    chips = "".join(f'<a class="pill good" style="text-decoration:none;margin:.2rem .3rem .2rem 0" '
                    f'href="/games/{g["id"]}/">{html.escape(g["title"])}</a>' for g in verified)
    body = f"""<header class="wrap" style="padding-block:4.5rem 2.5rem;text-align:center">
  <img src="/static/logo.png" alt="" style="width:120px;height:120px">
  <h1 style="font-size:clamp(2.6rem,7vw,4.2rem);margin:1rem 0 .5rem">Highball</h1>
  <p style="font-size:clamp(1.05rem,2.5vw,1.3rem);color:var(--ink2);max-width:34em;margin:0 auto">
    Run your Windows games on Apple Silicon. Free, open source, and honest about what works —
    down to which renderer each game needs.</p>
  <p style="margin:2.2rem 0 .75rem">
    <a class="btn" href="https://github.com/gauthierpiarrette/highball/releases/latest/download/Highball.dmg">Download for macOS</a></p>
  <p class="sub">notarized .dmg · auto-updating · Apple Silicon · macOS 14+ · GPL-3, no paid tier ever</p>
  <div style="margin:3rem auto 0;max-width:880px">
    <img src="/static/app.png" alt="Highball's Library: one cover grid across Steam and Epic with source badges and verified verdicts"
         style="border-radius:10px;border:1px solid var(--line);display:block">
  </div>
</header>

<section class="wrap">
  <div class="grid">
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">One click</span>
      <h3>Steam and Epic, ready to play</h3><p style="color:var(--ink2);font-size:.95rem">A verified Wine engine is assembled from pinned,
      checksummed upstream releases. Steam installs with one click; your Epic library connects and plays through the
      open-source Legendary client. .NET and VC++ runtimes are one click too.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Per-game verdicts</span>
      <h3>Your library, with answers</h3><p style="color:var(--ink2);font-size:.95rem">Games appear as cards with a verdict from the open
      database — verified, reported, predicted — and the renderer that actually works. Play launches with the right one.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Open data</span>
      <h3>A database, not a promise</h3><p style="color:var(--ink2);font-size:.95rem">Every claim carries its provenance and its date:
      verified on real hardware, reported upstream, or derived from ProtonDB crossed with anti-cheat data.
      <a href="/database/">Browse it</a> — it's yours to reuse.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Nothing to sign up for</span>
      <h3>No account, no telemetry</h3><p style="color:var(--ink2);font-size:.95rem">Highball asks for no login, phones nothing home,
      and keeps every bottle on your own disk. The app is GPL-3 and the data is open; neither can be taken away later.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Measured</span>
      <h3>Fast, and shown to be</h3><p style="color:var(--ink2);font-size:.95rem">msync-aware launching gave +42% frame rate on the reference
      machine, verified with Metal's own performance HUD. Frame caps and async shader compilation are one toggle away.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Built to last</span>
      <h3>Whisky's lesson, learned</h3><p style="color:var(--ink2);font-size:.95rem">No Wine fork, no binary hosting, engine-agnostic by design —
      the failure modes that ended Whisky are structurally removed. Engines update through a signed JSON manifest.</p></div>
  </div>
</section>

<section class="wrap">
  <h2 style="font-size:1.6rem;text-align:center;margin-bottom:1rem">Verified on real hardware</h2>
  <p style="text-align:center;color:var(--ink2);max-width:40em;margin:0 auto 1.2rem">
    {counts['verified-local']} games tested by hand on Apple Silicon, {counts['reported-upstream']} reported upstream,
    {counts['community']} from community consensus, {counts['blocked-anticheat']} honestly marked impossible —
    plus {derived_count:,} predictions.</p>
  <p style="text-align:center">{chips}</p>
  <p style="text-align:center;margin-top:1.2rem"><a class="btn ghost" href="/database/">Open the database</a></p>
</section>

<section class="wrap">
  <h2 style="font-size:1.6rem;text-align:center;margin-bottom:1rem">The honest part</h2>
  <p class="note bad" style="max-width:46em;margin:0 auto">
    <b>Kernel anti-cheat cannot work.</b> Valorant, Fortnite, Destiny 2, Call of Duty and friends load Windows
    kernel drivers that no compatibility layer can provide, on any Mac, in any app. Highball flags them
    <i>before</i> you download 80&nbsp;GB — and <a href="/docs/anti-cheat/">explains exactly why</a> rather than
    leaving you to find out.</p>
</section>"""
    B = base.rstrip("/")
    ld = [{"@context": "https://schema.org", "@type": "SoftwareApplication",
           "name": "Highball", "operatingSystem": "macOS 14+ (Apple Silicon)",
           "applicationCategory": "GameApplication", "url": B + "/",
           "downloadUrl": "https://github.com/gauthierpiarrette/highball/releases/latest/download/Highball.dmg",
           "license": "https://www.gnu.org/licenses/gpl-3.0.html",
           "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
           "description": "Free, open-source macOS app that runs Windows games on Apple Silicon."},
          {"@context": "https://schema.org", "@type": "WebSite", "name": "Highball", "url": B + "/",
           "potentialAction": {"@type": "SearchAction",
                               "target": {"@type": "EntryPoint",
                                          "urlTemplate": B + "/database/?q={search_term_string}"},
                               "query-input": "required name=search_term_string"}}]
    return layout(title="Highball — run Windows games on Apple Silicon",
                  desc="Free, open-source, notarized. One-click Steam and Epic, per-game renderer verdicts from an "
                       "open database, honest about anti-cheat. No account, no telemetry.",
                  path="/", body=body, base=base, jsonld=ld,
                  og_image=f"{base.rstrip('/')}/static/app.png")


# ---------------------------------------------------------------- content pages

def render_fragment(out, base, ctx, f, path, crumb_parent=None):
    """Render one content/*.html fragment. First line: <!-- title | meta description -->"""
    raw = open(f).read()
    m = re.match(r"\s*<!--(.*?)-->", raw, re.S)
    slug = os.path.basename(f)[:-5]
    meta = [x.strip() for x in m.group(1).split("|")] if m else [slug, ""]
    body = (raw[m.end():] if m else raw).format(**ctx)
    title, desc = meta[0], (meta[1] if len(meta) > 1 else "")
    B = base.rstrip("/")
    crumbs = '<p class="crumbs"><a href="/">Highball</a> › '
    items = [{"@type": "ListItem", "position": 1, "name": "Highball", "item": B + "/"}]
    if crumb_parent:
        crumbs += f'<a href="{crumb_parent[1]}">{html.escape(crumb_parent[0])}</a> › '
        items.append({"@type": "ListItem", "position": 2, "name": crumb_parent[0],
                      "item": B + crumb_parent[1]})
    short = title.split(" — ")[0].split(" | ")[0]
    crumbs += f"{html.escape(short)}</p>"
    items.append({"@type": "ListItem", "position": len(items) + 1, "name": short})
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}
    write(out, path, layout(title=title, desc=desc, path=path, base=base, jsonld=ld,
                            body=f'<div class="wrap prose">{crumbs}{body}</div>'))
    return title, desc


def content_pages(out, base, ctx):
    """content/*.html -> /docs/<slug>/ ; content/vs/*.html -> /vs/<slug>/ (+ a /vs/ index)."""
    made = []
    for f in sorted(glob.glob("content/*.html")):
        slug = os.path.basename(f)[:-5]
        path = f"/docs/{slug}/"
        render_fragment(out, base, ctx, f, path)
        made.append(path)

    vs = []
    for f in sorted(glob.glob("content/vs/*.html")):
        slug = os.path.basename(f)[:-5]
        path = f"/vs/{slug}/"
        title, desc = render_fragment(out, base, ctx, f, path, crumb_parent=("Compare", "/vs/"))
        vs.append((path, title, desc))
        made.append(path)

    if vs:
        cards = "".join(
            f'<a class="card" href="{p}" style="text-decoration:none;display:block">'
            f'<h3 style="margin:0 0 .4rem">{html.escape(t.split(" — ")[0].split(" | ")[0])}</h3>'
            f'<p style="color:var(--ink2);font-size:.92rem;margin:0">{html.escape(d)}</p></a>'
            for p, t, d in vs)
        body = f"""<div class="wrap">
<section style="padding-bottom:1rem">
<p class="crumbs"><a href="/">Highball</a> › Compare</p>
<h1 style="font-size:clamp(2rem,5vw,2.8rem);margin:.4rem 0 .6rem">How Highball compares</h1>
<p style="color:var(--ink2);max-width:46em">Honest comparisons, including the cases where the other tool is
the better choice. If you want commercial support and the broadest application coverage, buy
<a href="https://www.codeweavers.com/crossover">CrossOver</a> — it funds most of Wine's development, which
Highball depends on too.</p>
</section>
<div class="grid">{cards}</div>
</div>"""
        write(out, "/vs/", layout(title="How Highball compares to CrossOver, Parallels, Whisky and others",
                                  desc="Honest comparisons between Highball and the other ways to run Windows "
                                       "games on a Mac, including when the alternative is the better choice.",
                                  path="/vs/", body=body, base=base))
        made.append("/vs/")
    return made


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("HIGHBALL_DB", "../highball-db"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--base", default="https://gethighball.com")
    ap.add_argument("--no-predictions", action="store_true", help="skip the 12k prediction pages (fast builds)")
    a = ap.parse_args()

    if not os.path.isdir(f"{a.db}/db/games"):
        sys.exit(f"error: highball-db not found at {a.db} (pass --db or set HIGHBALL_DB)")

    data = load(a.db)
    games = data["games"]
    counts = {s: sum(1 for g in games if g.get("status") == s) for s in STATUS}
    derived = data["derived"].get("games", {})
    derived_count = len(derived)
    curated_slugs = {g["id"] for g in games}

    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out, exist_ok=True)
    shutil.copytree("static", os.path.join(a.out, "static"))
    # browsers request /favicon.ico by default; serve it from the root too
    shutil.copyfile("static/favicon.ico", os.path.join(a.out, "favicon.ico"))

    indexable = ["/", "/database/"]

    write(a.out, "/", landing_page(data, a.base, counts, derived_count))
    write(a.out, "/database/", database_page(data, a.base, counts, derived_count))

    lastmod = {}
    for g in games:
        write(a.out, f"/games/{g['id']}/", game_page(g, data, a.base))
        indexable.append(f"/games/{g['id']}/")
        if g.get("lastVerified"):
            lastmod[f"/games/{g['id']}/"] = g["lastVerified"]

    # predictions: one page per Steam appid, noindex until a Highball signal exists
    pred_index = {}
    if not a.no_predictions:
        used = set(curated_slugs)
        for appid, rec in derived.items():
            s = slugify(rec.get("title", "")) or f"app-{appid}"
            if s in used:
                s = f"{s}-{appid}"
            used.add(s)
            write(a.out, f"/games/{s}/", prediction_page(appid, rec, a.base, s))
            p = PRED_LABEL.get(rec.get("macPrediction", "maybe"), ("Unknown", "warn"))
            pred_index[appid] = {"t": rec.get("title", ""), "s": s, "p": p[0], "c": p[1],
                                 "pt": rec.get("protonTier", "?"), "n": rec.get("recentReports", 0)}
    os.makedirs(os.path.join(a.out, "data"), exist_ok=True)
    json.dump(pred_index, open(os.path.join(a.out, "data/predictions.json"), "w"), separators=(",", ":"))

    ctx = {"verified": counts["verified-local"], "curated": len(games),
           "derived": f"{derived_count:,}", "blocked": counts["blocked-anticheat"],
           "year": datetime.date.today().year}
    indexable += content_pages(a.out, a.base, ctx)

    # 404: GitHub Pages serves this with a real 404 status, which keeps Google
    # from treating missing pages as soft-404 duplicates of the homepage.
    nf = """<div class="wrap prose" style="padding-top:3rem">
<h1>That page isn't here</h1>
<p>The link may be old, or the game may not be in the database under that name yet.</p>
<ul>
  <li><a href="/database/">Search the compatibility database</a> — 101 curated games plus predictions for
      thousands more.</li>
  <li><a href="/docs/install/">Install Highball</a></li>
  <li><a href="/docs/troubleshooting/">Troubleshooting</a></li>
  <li><a href="/">Back to the start</a></li>
</ul>
<p class="sub">If something on this site linked you here, that's a bug worth
<a href="https://github.com/gauthierpiarrette/highball-website/issues">reporting</a>.</p></div>"""
    open(os.path.join(a.out, "404.html"), "w").write(
        layout(title="Page not found — Highball", desc="That page isn't here. Search the Mac game "
               "compatibility database or head back to the start.", path="/404.html",
               body=nf, base=a.base, noindex=True))

    # sitemap: indexable pages only (predictions are deliberately excluded)
    today = datetime.date.today().isoformat()
    urls = "".join(
        f"<url><loc>{a.base.rstrip('/')}{p}</loc><lastmod>{lastmod.get(p, today)}</lastmod></url>"
        for p in indexable)
    open(os.path.join(a.out, "sitemap.xml"), "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    open(os.path.join(a.out, "robots.txt"), "w").write(
        f"User-agent: *\nAllow: /\n\nSitemap: {a.base.rstrip('/')}/sitemap.xml\n")
    host = re.sub(r"^https?://", "", a.base).strip("/")
    open(os.path.join(a.out, "CNAME"), "w").write(host + "\n")
    open(os.path.join(a.out, ".nojekyll"), "w").write("")

    print(f"built {len(indexable)} indexable pages + {len(pred_index)} predictions -> {a.out}/")
    print(f"  curated {len(games)} (verified {counts['verified-local']}, blocked {counts['blocked-anticheat']})")


if __name__ == "__main__":
    main()
