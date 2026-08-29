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
        r = json.load(open(f))          # a malformed recipe should fail the build, not vanish
        if "id" not in r:
            sys.exit(f"error: recipe {f} has no id")
        d["recipes"][r["id"]] = r
    d["reports"] = {}
    for f in glob.glob(f"{dbpath}/db/reports/*.jsonl"):
        slug = os.path.basename(f)[:-6]
        rows = [json.loads(l) for l in open(f) if l.strip()]
        rows.sort(key=lambda r: r.get("date") or "")   # oldest first, so reversed() = newest first
        d["reports"][slug] = rows
    # Required inputs: a malformed file must fail the build, not silently publish an empty site.
    d["derived"] = json.load(open(f"{dbpath}/db/derived/derived.json"))
    d["anticheat"] = json.load(open(f"{dbpath}/db/anticheat.json"))
    return d


# ---------------------------------------------------------------- layout

def layout(*, title, desc, path, body, base, noindex=False, og_image=None, jsonld=None,
           extra_head="", wide=False):
    """Wrap a body fragment in the site chrome. `path` is the absolute site path with trailing slash."""
    url = base.rstrip("/") + path
    og = og_image or f"{base.rstrip('/')}/static/og.jpg"
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
        # json.dumps does not escape < or &, so db-controlled text containing "</script>"
        # would break out of the block. These escapes are valid JSON.
        def safe(o):
            return (json.dumps(o).replace("<", "\\u003c").replace(">", "\\u003e")
                    .replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
        ld = "".join(f'<script type="application/ld+json">{safe(o)}</script>' for o in graph)
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
<a class="skip" href="#main">Skip to content</a>
<div class="topbar"><div class="wrap {'wrap-wide' if wide else ''} row">
  <a class="brand" href="/"><img src="/static/logo-128.png" width="26" height="26" alt="">Highball</a>
  <nav>{navhtml}</nav>
  <a class="dl" href="https://github.com/gauthierpiarrette/highball/releases/latest/download/Highball.dmg">Download</a>
</div></div>
<main id="main">{body}</main>
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


RENDERER_GLOSS = {
    "dxvk": "Direct3D 9-11 over Vulkan",
    "dxmt": "Direct3D 11 over Metal",
    "d3dmetal": "Apple's Game Porting Toolkit",
}


def renderer_matrix(game, reports):
    """Honest matrix: what we know per renderer, graded by how good the evidence actually is."""
    rec = (game.get("renderer") or "").lower()
    status = game.get("status", "community")
    verified = status == "verified-local"
    rec_pill = "good" if verified else "info"
    rec_label = "Recommended" if verified else "Reported"
    seen = {}
    for r in reports:
        rr = (r.get("renderer") or "").lower()
        if rr:
            seen.setdefault(rr, []).append(r)
    rows = []
    for r in RENDERERS:
        label = f'{RENDERER_LABEL[r]}<span class="prov">{RENDERER_GLOSS[r]}</span>'
        if r == rec:
            n = len(seen.get(r, []))
            if n:
                detail = f"{n} report{'s' if n != 1 else ''}"
            elif verified:
                detail = "run by Highball on Apple Silicon"
            elif status == "reported-upstream":
                detail = "named in upstream release notes"
            else:
                detail = "community reports"
            rows.append(f'<tr><td class="r">{label}</td>'
                        f'<td><span class="pill {rec_pill}">{rec_label}</span></td>'
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
    return ('<div class="tablewrap" tabindex="0" role="region" aria-label="Renderer verdicts">'
            '<table class="matrix"><thead><tr><th>Renderer</th><th>Verdict</th>'
            '<th>Evidence</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


TIER_VERB = {
    "verified-local":    "Verified by Highball on Apple Silicon",
    "reported-upstream": "Reported working upstream, not yet run by Highball",
    "community":         "Reported working by the community, not yet run by Highball",
}


def faq_entries(title, game, blocked, label, stamp, has_recipe):
    """Real questions people type, answered in one paragraph each.
    Every answer must be true of the actual data — these are surfaced standalone by search engines."""
    def qa(q, a):
        return {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
    nm = game.get("nativeMac") or {}
    out = []
    if blocked:
        if nm.get("available"):
            out.append(qa(f"Does {title} work on Mac?",
                          f"Yes, but not through a compatibility layer. {nm.get('where', 'The publisher')} ships a "
                          f"native macOS build, and that is what you should install. The Windows build cannot run "
                          f"under Highball, CrossOver, Whisky or a virtual machine, because its anti-cheat needs a "
                          f"Windows kernel driver that macOS will never load."))
        else:
            out.append(qa(f"Does {title} work on Mac?",
                          f"No. {title} uses kernel-level anti-cheat, which needs a Windows kernel driver. "
                          f"Compatibility layers such as Highball, CrossOver and Whisky run entirely in user space, "
                          f"so there is nothing for that driver to load into, and virtual machines have the same "
                          f"limit. Cloud streaming runs the real Windows build remotely, which is why it works."))
            out.append(qa(f"Can I play {title} on Mac with CrossOver or Parallels?",
                          "No. The same limit applies to every compatibility layer and to virtual machines: the "
                          "anti-cheat driver cannot load. Streaming is the only route."))
    else:
        rec = game.get("renderer")
        status = game.get("status", "community")
        if status == "verified-local":
            evidence = (f"Highball has run it on Apple Silicon"
                        + (f" ({stamp})" if game.get("lastVerified") else "") + ".")
        elif status == "reported-upstream":
            evidence = ("It is named as working or fixed in upstream release notes. Highball has not run it, "
                        "so treat this as a strong report rather than a verified result.")
        else:
            evidence = ("This comes from community reports rather than a Highball test run, so treat it as a "
                        "reasonable expectation rather than a guarantee.")
        out.append(qa(f"Does {title} work on Mac?", f"{title} has no native Mac build, but it is reported to run "
                                                    f"on Apple Silicon through Highball, a free open-source "
                                                    f"compatibility layer. {evidence}"
                      if not nm.get("available") else
                      f"Yes. {nm.get('where', 'The publisher')} ships a native macOS build, which will beat running "
                      f"the Windows version through any compatibility layer. {nm.get('note', '')}"))
        if rec:
            r = RENDERER_LABEL.get(rec, rec)
            out.append(qa(f"Which renderer should I use for {title}?",
                          f"{r}. Highball can translate Direct3D through DXVK, DXMT or Apple's D3DMetal, and the "
                          f"right choice varies by game. The database records {r} for {title}"
                          + (f", and applying the {title} recipe sets it for you." if has_recipe
                             else ". Set it in the bottle's settings before you launch.")))
        if has_recipe:
            out.append(qa(f"Is there a one-click setup for {title}?",
                          f"Yes. Highball ships a recipe for {title} that sets the tested renderer and any per-game "
                          f"fixes. Open the game in your Library and apply it."))
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
    if blocked:
        stamp = "structural, not a test result"
    elif last:
        bits = [f"last confirmed {last}"]
        if engine: bits.append(f"engine {engine}")
        if macos: bits.append(f"macOS {macos}")
        stamp = " · ".join(bits)
    else:
        stamp = "no dated Highball run yet"

    nm = game.get("nativeMac") or {}
    if blocked and nm.get("available"):
        verdict = (f"<b>Play the native Mac version.</b> {html.escape(nm.get('where', 'The publisher'))} ships an "
                   f"official macOS build of {html.escape(title)}. The <i>Windows</i> build cannot run under "
                   f"Highball, CrossOver, Whisky or a virtual machine, because its anti-cheat loads a Windows "
                   f"kernel driver, but you do not need it.")
    elif blocked:
        verdict = (f"<b>{html.escape(title)} cannot run on a Mac through Highball, CrossOver, Whisky, "
                   f"or any other compatibility layer.</b> Its anti-cheat loads a Windows kernel driver, "
                   f"and macOS will never load one. This is not a bug anyone can fix.")
    else:
        rec = game.get("renderer")
        verb = TIER_VERB.get(status, "Reported working")
        verdict = (f"<b>{verb}</b>"
                   + (f", using the <b>{RENDERER_LABEL.get(rec, rec)}</b> renderer" if rec else "")
                   + f". {html.escape(meaning)}")

    art = steam_art(appid)
    head = f"""<div class="wrap">
<p class="crumbs"><a href="/">Highball</a> › <a href="/database/">Database</a> › {html.escape(title)}</p>
<div class="gamehead">
  {f'<img class="art" src="{art}" width="460" height="215" alt="" referrerpolicy="no-referrer">' if art else ''}
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

    if nm.get("available"):
        where = html.escape(nm.get("where", "the publisher"))
        link = nm.get("url")
        body.append(f"""<div class="note good"><b>There is a native Mac build.</b>
        {html.escape(nm.get('note', ''))} It is on {where}
        {f'(<a href="{html.escape(link)}">official page</a>)' if link else ''}. A native build runs straight on
        Metal with nothing translating in between, so it will beat anything on this page.
        <a href="/docs/native-mac-games/">Other games in the same situation</a>.</div>""")

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
        if last and engine:
            body.append(f'<p class="sub" style="margin-top:.7rem">{html.escape(stamp)}. Dated runs record the '
                        f'engine build and, where the reporter gave it, the macOS version.</p>')
        else:
            body.append('<p class="sub" style="margin-top:.7rem">No dated Highball run yet. When one lands it '
                        'records the renderer, the engine build and the macOS version it was seen on — which is '
                        'what stops a verdict quietly rotting. '
                        '<a href="https://github.com/gauthierpiarrette/highball-db/issues/new?template=report.yml">'
                        'Send one</a>.</p>')

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

    # FAQ must be visible on the page: FAQPage schema whose answers exist only in JSON-LD is
    # non-compliant, and the content is genuinely useful anyway.
    faqs = faq_entries(title, game, blocked, label, stamp, bool(recipe))
    if faqs:
        qa_html = "".join(
            f'<h3>{html.escape(f["name"])}</h3><p>{html.escape(f["acceptedAnswer"]["text"])}</p>'
            for f in faqs)
        body.append(f"<h2>Common questions</h2>{qa_html}")

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
          {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faqs}]
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
  {f'<img class="art" src="{art}" width="460" height="215" alt="" referrerpolicy="no-referrer">' if art else ''}
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
<div class="tablewrap" tabindex="0" role="region" aria-label="Curated games"><table>
<thead><tr><th>Game</th><th>Status</th><th>Renderer</th><th>Last confirmed</th><th class="num">Reports</th></tr></thead>
<tbody id="rows">{"".join(row(g) for g in games)}</tbody></table></div>
<p class="sub" id="empty" role="status" aria-live="polite" style="display:none;padding:1rem">No curated entry matches. It may still have a prediction below.</p>

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
<p class="sub" id="dhint" role="status" aria-live="polite" style="padding:.6rem 0">Type at least two characters.</p>
</section>
</div>
<script>
const rows=[...document.querySelectorAll('#rows tr')];let f=null,q='';
function apply(){{let n=0;rows.forEach(r=>{{const ok=(!f||r.dataset.status===f)&&(!q||r.dataset.t.includes(q));r.style.display=ok?'':'none';if(ok)n++;}});
document.getElementById('empty').style.display=n?'none':'block';}}
document.querySelector('.tiles').addEventListener('click',e=>{{const b=e.target.closest('.tile');if(!b)return;
const k=b.dataset.f;f=(f===k)?null:k;document.querySelectorAll('.tile').forEach(t=>t.setAttribute('aria-pressed',t.dataset.f===f));apply();}});
const qi=document.getElementById('q');
qi.addEventListener('input',e=>{{q=e.target.value.toLowerCase().trim();apply();}});
const qp=new URLSearchParams(location.search).get('q');
if(qp){{qi.value=qp;q=qp.toLowerCase().trim();apply();}}
let Dp=null,seq=0,timer;const dq=document.getElementById('dq');
const loadD=()=>Dp||(Dp=fetch('/data/predictions.json').then(r=>{{if(!r.ok)throw 0;return r.json();}})
  .then(j=>j.games).catch(e=>{{Dp=null;throw e;}}));
dq.addEventListener('input',e=>{{clearTimeout(timer);const v=e.target.value.toLowerCase().trim();timer=setTimeout(()=>run(v),160);}});
async function run(v){{const my=++seq;
const wrap=document.getElementById('dwrap'),hint=document.getElementById('dhint');
if(v.length<2){{wrap.style.display='none';hint.style.display='block';hint.textContent='Type at least two characters.';return;}}
let D;
hint.style.display='block';hint.textContent='Searching predictions…';
try{{D=await loadD();}}catch(err){{if(my!==seq)return;hint.textContent='Could not load predictions. Try again, or browse the data on GitHub.';return;}}
if(my!==seq)return;
const hits=Object.entries(D).filter(([id,g])=>g.t.toLowerCase().includes(v)).slice(0,80);
document.getElementById('drows').innerHTML=hits.map(([id,g])=>
`<tr><td class="t"><a href="/games/${{g.s}}/">${{g.t.replace(/</g,'&lt;')}}</a></td><td><span class="pill ${{g.c}}">${{g.p}}</span></td><td class="mono">${{g.pt}}</td><td class="num">${{g.n}}</td></tr>`).join('');
wrap.style.display=hits.length?'':'none';
hint.textContent=hits.length?(hits.length+' prediction'+(hits.length>1?'s':'')+' shown'):'No prediction for that title.';
hint.style.display='block';}}
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
    <img src="/static/app.jpg" width="1600" height="1088" fetchpriority="high"
         alt="Highball's Library: one cover grid across Steam and Epic with source badges and verified verdicts"
         style="border-radius:10px;border:1px solid var(--line);display:block">
  </div>
</header>

<section class="wrap">
  <div class="grid">
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">One click</span>
      <h2 style="font-size:1.15rem;margin:0 0 .5rem">Steam and Epic, ready to play</h2><p style="color:var(--ink2);font-size:.95rem">A verified Wine engine is assembled from pinned,
      checksummed upstream releases. Steam installs with one click; your Epic library connects and plays through the
      open-source Legendary client. .NET and VC++ runtimes are one click too.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Per-game verdicts</span>
      <h2 style="font-size:1.15rem;margin:0 0 .5rem">Your library, with answers</h2><p style="color:var(--ink2);font-size:.95rem">Games appear as cards with a verdict from the open
      database: verified, reported or predicted, plus the renderer other people got working. Recipes set it for the games that have one.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Open data</span>
      <h2 style="font-size:1.15rem;margin:0 0 .5rem">A database, not a promise</h2><p style="color:var(--ink2);font-size:.95rem">Every claim carries its provenance, and its date where one exists:
      verified on real hardware, reported upstream, or derived from ProtonDB crossed with anti-cheat data.
      <a href="/database/">Browse it</a> — it's yours to reuse.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Nothing to sign up for</span>
      <h2 style="font-size:1.15rem;margin:0 0 .5rem">No account, no telemetry</h2><p style="color:var(--ink2);font-size:.95rem">Highball asks for no login, phones nothing home,
      and keeps every bottle on your own disk. The app is GPL-3 and the data is open; neither can be taken away later.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Measured</span>
      <h2 style="font-size:1.15rem;margin:0 0 .5rem">Tuned where it counts</h2><p style="color:var(--ink2);font-size:.95rem">Launches use the faster in-process
      synchronisation path where the game tolerates it, which is worth real frame rate on CPU-bound titles.
      Frame caps and async shader compilation are one toggle away.</p></div>
    <div class="card"><span class="mono" style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)">Built to last</span>
      <h2 style="font-size:1.15rem;margin:0 0 .5rem">Whisky's lesson, learned</h2><p style="color:var(--ink2);font-size:.95rem">No Wine fork, no binary hosting, engine-agnostic by design —
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
                  og_image=f"{base.rstrip('/')}/static/og.jpg")


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
        # A curated entry always wins: never publish a Linux-derived guess for a game we
        # already have a real verdict on (it would contradict the curated page).
        curated_appids = {str(g.get("steam_appid")) for g in games if g.get("steam_appid")}
        curated_titles = {g["title"].strip().lower() for g in games}
        for appid, rec in derived.items():
            if str(appid) in curated_appids or rec.get("title", "").strip().lower() in curated_titles:
                continue
            s = slugify(rec.get("title", "")) or f"app-{appid}"
            if s in used:
                s = f"{s}-{appid}"
            used.add(s)
            write(a.out, f"/games/{s}/", prediction_page(appid, rec, a.base, s))
            p = PRED_LABEL.get(rec.get("macPrediction", "maybe"), ("Unknown", "warn"))
            pred_index[appid] = {"t": rec.get("title", ""), "s": s, "p": p[0], "c": p[1],
                                 "pt": rec.get("protonTier", "?"), "n": rec.get("recentReports", 0)}
    os.makedirs(os.path.join(a.out, "data"), exist_ok=True)
    # ODbL requires the licence and attribution to travel with the derived database.
    json.dump({
        "license": "ODbL-1.0",
        "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "source": "Derived from ProtonDB community reports (https://github.com/bdefore/protondb-data), "
                  "crossed with AreWeAntiCheatYet data (MIT).",
        "note": "Proton describes Linux, not macOS. These are odds, not verdicts, and no Mac verification "
                "stands behind them.",
        "generated": datetime.date.today().isoformat(),
        "count": len(pred_index),
        "games": pred_index,
    }, open(os.path.join(a.out, "data/predictions.json"), "w"), separators=(",", ":"))

    # Curated data as clean JSON: the part that is CC0 and worth quoting.
    json.dump({
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "source": "https://github.com/gauthierpiarrette/highball-db",
        "note": "Curated compatibility data for running Windows games on Apple Silicon. Each entry carries "
                "its provenance. anticheat fields are derived from AreWeAntiCheatYet (MIT).",
        "generated": datetime.date.today().isoformat(),
        "status_meanings": {k: v[2] for k, v in STATUS.items()},
        "count": len(games),
        "games": [{
            "id": g["id"], "title": g["title"], "status": g.get("status"),
            "steam_appid": g.get("steam_appid"), "renderer": g.get("renderer"),
            "lastVerified": g.get("lastVerified"), "provenance": g.get("provenance"),
            "notes": g.get("notes"), "anticheat": g.get("anticheat"),
            "reports": len(data["reports"].get(g["id"], [])),
            "recipe": g["id"] in data["recipes"],
            "url": f"{a.base.rstrip('/')}/games/{g['id']}/",
        } for g in games],
    }, open(os.path.join(a.out, "data/games.json"), "w"), indent=1)

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
    # Only emit lastmod where a real date exists. Stamping today's build date on every URL
    # trains crawlers to ignore the signal entirely.
    def entry(p):
        d = lastmod.get(p)
        return (f"<url><loc>{a.base.rstrip('/')}{p}</loc>"
                + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>")
    urls = "".join(entry(p) for p in indexable)
    open(os.path.join(a.out, "sitemap.xml"), "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    # robots: explicitly welcome AI/answer-engine crawlers. The compatibility data is open
    # (CC0 / ODbL) and meant to be reused, including by assistants answering "does X run on Mac".
    ai_agents = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User",
                 "Claude-SearchBot", "anthropic-ai", "PerplexityBot", "Perplexity-User",
                 "Google-Extended", "Applebot-Extended", "CCBot", "Bingbot", "DuckDuckBot",
                 "Amazonbot", "meta-externalagent", "cohere-ai", "YouBot"]
    robots = ["# Highball compatibility data is open and meant to be reused.",
              "# Curated data CC0, predictions ODbL 1.0 (attribute ProtonDB), anti-cheat data MIT.",
              "# Machine-readable: /data/games.json, /data/predictions.json, /llms.txt", "",
              "User-agent: *", "Allow: /", ""]
    for ua in ai_agents:
        robots += [f"User-agent: {ua}", "Allow: /", ""]
    robots += [f"Sitemap: {a.base.rstrip('/')}/sitemap.xml", ""]
    open(os.path.join(a.out, "robots.txt"), "w").write("\n".join(robots))

    # llms.txt — curated map of the site for language models (llmstxt.org convention)
    B = a.base.rstrip("/")
    verified_list = "\n".join(
        f"- [{g['title']}]({B}/games/{g['id']}/): verified on Apple Silicon"
        + (f", renderer {RENDERER_LABEL.get(g.get('renderer'), g.get('renderer'))}" if g.get("renderer") else "")
        + (f", last confirmed {g['lastVerified']}" if g.get("lastVerified") else "")
        for g in games if g["status"] == "verified-local")
    open(os.path.join(a.out, "llms.txt"), "w").write(f"""# Highball

> Highball is a free, open-source macOS app that runs Windows games on Apple Silicon, plus an open
> compatibility database recording which games work, which Direct3D translation layer (DXVK, DXMT or
> Apple's D3DMetal) each one needs, and when that was last confirmed. Curated data is CC0 and may be
> reused and quoted freely.

Scope and honesty notes, which matter if you are answering a question from this data:
- {len(games)} games are curated: {counts['verified-local']} verified by hand on real Apple Silicon hardware,
  {counts['reported-upstream']} reported upstream, {counts['community']} from community consensus,
  {counts['blocked-anticheat']} blocked by kernel anti-cheat.
- A further {derived_count:,} Steam titles carry only a machine-derived prediction from Linux/Proton data
  crossed with anti-cheat data. Those are odds, not verdicts, and should be described as such.
- Kernel-level anti-cheat (Vanguard, Ricochet, kernel modes of Easy Anti-Cheat and BattlEye) cannot work
  under any macOS compatibility layer, because it needs a Windows kernel driver. This is architectural and
  applies to CrossOver, Whisky and virtual machines too. Userspace cases vary per title, so do not state a
  blanket rule per anti-cheat vendor.
- Highball requires Apple Silicon and macOS 14 or newer. It is GPL-3, needs no account, and sends no telemetry.

## Data (machine-readable)
- [Curated game data, JSON]({B}/data/games.json): the {len(games)} curated entries, CC0.
- [Predictions, JSON]({B}/data/predictions.json): {derived_count:,} ProtonDB-derived predictions, ODbL 1.0.
- [Source repository](https://github.com/gauthierpiarrette/highball-db): the whole database as plain JSON.
- [How the data works]({B}/docs/data/): provenance tiers, per-renderer verdicts, freshness, licensing.

## Key pages
- [Compatibility database]({B}/database/): searchable, all curated entries and predictions.
- [Anti-cheat on a Mac]({B}/docs/anti-cheat/): what can and cannot work, and why.
- [Games that already run natively on Mac]({B}/docs/native-mac-games/): check before using any compatibility layer.
- [Xbox Game Pass on a Mac]({B}/docs/game-pass/): what streams, what cannot be installed.
- [Install Highball]({B}/docs/install/) · [Troubleshooting]({B}/docs/troubleshooting/) · [Credits]({B}/docs/credits/)

## Comparisons
- [Switching from Whisky]({B}/vs/whisky/) · [vs CrossOver]({B}/vs/crossover/) · [vs Parallels]({B}/vs/parallels/)
- [vs GameSir GameHub]({B}/vs/gamehub/) · [vs Pixel Port]({B}/vs/pixel-port/) · [vs Porting Kit]({B}/vs/porting-kit/)

## Verified games
{verified_list}
""")
    host = re.sub(r"^https?://", "", a.base).strip("/")
    open(os.path.join(a.out, "CNAME"), "w").write(host + "\n")
    open(os.path.join(a.out, ".nojekyll"), "w").write("")

    print(f"built {len(indexable)} indexable pages + {len(pred_index)} predictions -> {a.out}/")
    print(f"  curated {len(games)} (verified {counts['verified-local']}, blocked {counts['blocked-anticheat']})")


if __name__ == "__main__":
    main()
