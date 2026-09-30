#!/usr/bin/env python3
"""Highball's static, multilingual website. Python standard library only."""
import argparse
from collections import Counter
import datetime as dt
import html
import json
from pathlib import Path
import re
import shutil
from string import Template
import catalog
from urllib.parse import urlsplit, urlencode

HERE = Path(__file__).resolve().parent
LANGUAGES = {'en':'English', 'es':'Español', 'ru':'Русский', 'zh':'简体中文', 'ja':'日本語', 'ko':'한국어', 'pt':'Português'}
REPO = 'https://github.com/gauthierpiarrette/highball'
DB_REPO = 'https://github.com/gauthierpiarrette/highball-db'
DOWNLOAD = REPO + '/releases/latest/download/Highball.dmg'
REPORT = DB_REPO + '/issues/new?template=report.yml'
ORDER = {'verified-local':0, 'reported-upstream':1, 'community':2, 'blocked-anticheat':3, 'blocked-publisher':4}
ICONS = {
 'apple':'<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.8 12.8c0-2.4 2-3.6 2.1-3.7-1.2-1.8-3-2-3.7-2-1.6-.2-3.1.9-3.9.9-.8 0-2-1-3.3-.9-1.7 0-3.3 1-4.2 2.5-1.8 3.1-.5 7.7 1.2 10.2.9 1.3 1.8 2.6 3.2 2.5 1.3 0 1.8-.8 3.5-.8 1.6 0 2.1.8 3.6.8s2.4-1.2 3.2-2.5c1-1.4 1.4-2.8 1.4-2.9-.1 0-3.1-1.2-3.1-4.1ZM14.3 5.5c.7-.9 1.2-2.1 1.1-3.3-1.1 0-2.4.7-3.2 1.6-.7.7-1.3 2-1.1 3.1 1.2.1 2.4-.6 3.2-1.4Z"/></svg>',
 'github':'<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.86c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.89 1.52 2.34 1.08 2.91.83.09-.65.35-1.08.64-1.33-2.22-.25-4.56-1.11-4.56-4.95 0-1.1.39-2 1.03-2.7-.1-.25-.45-1.28.1-2.67 0 0 .84-.27 2.75 1.03A9.6 9.6 0 0 1 12 6.9c.85 0 1.7.11 2.5.34 1.91-1.3 2.75-1.03 2.75-1.03.55 1.39.2 2.42.1 2.67.64.7 1.03 1.6 1.03 2.7 0 3.85-2.34 4.7-4.57 4.95.36.31.68.92.68 1.85v2.63c0 .26.18.58.69.48A10 10 0 0 0 12 2Z"/></svg>',
 'searchIcon':'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>',
 'lock':'<svg viewBox="0 0 64 64" aria-hidden="true"><rect x="14" y="27" width="36" height="28" rx="8"/><path d="M22 27V19a10 10 0 0 1 20 0v8"/><circle cx="32" cy="39" r="2"/><path d="M32 41v6"/></svg>'
}

def esc(value):
    return html.escape(str(value), quote=True)

def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

def slugify(title):
    return re.sub(r'[^a-z0-9]+','-',re.sub(r"[’'`]",'',title.lower())).strip('-')[:80] or 'game'

def load_data(db):
    games = [json.loads(f.read_text()) for f in sorted((db/'db/games').glob('*.json'))]
    if not games:
        raise ValueError(f'No games at {db}/db/games. Clone highball-db first.')
    for game in games:
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]*',game['id']) or game.get('status') not in ORDER:
            raise ValueError(f'Invalid game identifier or status: {game}')
    games.sort(key=lambda g:(ORDER.get(g.get('status'),9),g['title'].casefold()))
    derived = json.loads((db/'db/derived/derived.json').read_text())
    anticheat = json.loads((db/'db/anticheat.json').read_text())
    recipes = {}
    for f in (db/'recipes').glob('*/*.json'):
        recipe=json.loads(f.read_text())
        recipes[recipe['id']] = {'path':str(f.relative_to(db)), 'data':recipe}
    reports = {}
    for f in (db/'db/reports').glob('*.jsonl'):
        reports[f.stem] = sorted([json.loads(l) for l in f.read_text().splitlines() if l.strip()],key=lambda r:r.get('date',''),reverse=True)
    appids = {str(g.get('steam_appid')) for g in games if g.get('steam_appid')}
    titles = {g['title'].strip().casefold() for g in games}
    blocked_ids={str(g.get('steam_appid')) for g in games if g.get('steam_appid') and g.get('status')=='blocked-anticheat'}
    anti_by_id={str(g.get('steam_appid')):g for g in anticheat['games'].values() if g.get('steam_appid')}
    predictions=[]
    used={g['id'] for g in games}
    for appid,rec in derived['games'].items():
        if str(appid) in appids or rec.get('title','').strip().casefold() in titles: continue
        slug=slugify(rec.get('title',''))
        if slug in used: slug=f'{slug}-{appid}'
        used.add(slug)
        anti=anti_by_id.get(str(appid),{})
        verdict=rec.get('macPrediction','maybe')
        if str(appid) in blocked_ids or anti.get('macVerdict')=='blocked': verdict='blocked'
        predictions.append({'id':slug, 'title':rec['title'], 'steam_appid':appid, 'status':'prediction', 'prediction':verdict, 'protonTier':rec.get('protonTier'), 'reports':rec.get('recentReports',0), 'anticheat':rec.get('anticheat',anti.get('anticheats',[]))})
    return games, predictions, derived, anticheat, recipes, reports

class Builder:
    def __init__(self,args):
        self.out=Path(args.out).resolve()
        self.base=args.base.rstrip('/')
        url=urlsplit(self.base)
        if url.scheme not in ('http','https') or not url.netloc or url.query or url.fragment:
            raise ValueError('--base must be an absolute HTTP(S) URL, optionally including a repository subpath.')
        self.root=url.path.rstrip('/')
        self.media=json.loads((HERE/'media.json').read_text())
        for asset in [self.media['hero']['file'],self.media['app'],self.media['dlss']['original'],self.media['dlss']['upscaled'], *[f for f in self.media['covers'].values() if f]]:
            target=(HERE/'static'/asset).resolve()
            if not target.is_relative_to(HERE/'static') or not target.is_file(): raise ValueError(f'Missing or invalid media asset: {asset}')
        self.locales={lang:json.loads((HERE/'locales'/f'{lang}.json').read_text()) for lang in LANGUAGES}
        for lang,pack in self.locales.items():
            if set(pack)!=set(self.locales['en']): raise ValueError(f'Incomplete locale: {lang}')
        self.games,self.predictions,self.derived,self.anticheat,self.recipes,self.reports=load_data(Path(args.db).resolve())
        self.counts=Counter(g['status'] for g in self.games)
        self.sitemap=[]
        self.catalog=catalog.read_cache(getattr(args,'catalog',None) or HERE/'.cache/steam.json')

    def path(self,lang,route=''):
        return f"{self.root}/" + (f'{lang}/' if lang!='en' else '') + route

    def translate(self,body,lang):
        pack=self.locales[lang]
        def sub(m):
            if m[1] not in pack: raise ValueError(f'Missing translation {m[1]}')
            return esc(pack[m[1]]).replace('\n','<br>')
        return re.sub(r'\{\{([\w-]+)\}\}',sub,body)

    def write(self,path,body):
        target=self.out/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(body,encoding='utf-8')

    def card(self,g,lang,i=0):
        t=self.locales[lang]
        status=g['status']
        label=t['communityStatus' if status=='community' else status]
        style=['ember','forest','portal','violet'][i%4]
        symbol=['✦','◈','◌','✧'][i%4]
        href=self.path(lang,f"games/{g['id']}/")
        card = f'<a class="game-card {style}" href="{esc(href)}"><div class="game-art"><span class="card-grain"></span><span class="art-orb"></span><span class="art-landscape"></span><span class="art-symbol" aria-hidden="true">{symbol}</span><span class="placeholder-label">{esc(t["placeholder"])}</span><span class="game-art-title">{esc(g["title"])}</span><span class="game-card-arrow" aria-hidden="true">↗</span></div><div class="game-card-meta"><h3>{esc(g["title"])}</h3><span class="status-pill {status}"><i></i>{esc(label)}</span></div></a>'

        meta=catalog.metadata(self.catalog,g.get('steam_appid'),lang)
        candidates=catalog.cover_candidates(g.get('steam_appid'),meta,self.media['covers'].get(g['id']),self.root)
        if candidates:
            image=f'<img class="game-cover" src="{esc(candidates[0])}" data-artwork data-fallbacks="{esc(safe_json(candidates[1:]))}" alt="" loading="lazy" decoding="async" width="600" height="900" referrerpolicy="no-referrer">'
            card=card.replace('<div class="game-art">','<div class="game-art">'+image,1)
        if meta.get('genres'):
            tags=' · '.join(meta['genres'][:2])
            card=card.replace('</div></a>',f'<small class="card-genres" lang="{esc(meta.get("language","en"))}">{esc(tags)}</small></div></a>')
        return card

    def render(self,lang,route,body,title=None,desc=None,page='home',noindex=False,substitutions=None,search_mode=None):
        t=self.locales[lang]
        canonical=self.base+'/' + (f'{lang}/' if lang!='en' else '') + route
        config={'lang':lang,'root':self.root,'home':self.path(lang),'database':self.path(lang,'database/'),'languages':list(LANGUAGES),'detectLanguage':route=='' and lang=='en','route':route,'translations':{k:t[k] for k in ['all','verified-local','reported-upstream','communityStatus','blocked-anticheat','blocked-publisher','prediction','likely','maybe','unlikely','blocked','results','more','empty','loading','error','retry','predictionNote','placeholder','viewGame','reports','resultOne','mediaCredit','viewSteam','openScreenshot','imageCount']}}
        if search_mode: config['searchMode']=search_mode
        lang_options=''.join(f'<option value="{code}" {"selected" if code==lang else ""}>{code.upper() if code==lang else code.upper()+" · "+esc(name)}</option>' for code,name in LANGUAGES.items())
        schema={'@context':'https://schema.org','@type':'WebPage','name':title or t['metaTitle'],'url':canonical,'inLanguage':lang}
        if page=='home': schema={'@context':'https://schema.org','@type':'SoftwareApplication','name':'Highball','applicationCategory':'GameApplication','operatingSystem':'macOS 14+ (Apple Silicon)','url':canonical,'downloadUrl':DOWNLOAD,'license':REPO+'/blob/main/LICENSE','offers':{'@type':'Offer','price':'0','priceCurrency':'USD'}}
        schema.update(description=desc or t['metaDescription'],inLanguage=lang)
        alternates=''.join(f'<link rel="alternate" hreflang="{code}" href="{self.base}/{"" if code=="en" else code+"/"}{route}">' for code in LANGUAGES)
        alternates+=f'<link rel="alternate" hreflang="x-default" href="{self.base}/{route}">'
        values={'lang':lang,'title':esc(title or t['metaTitle']),'description':esc(desc or t['metaDescription']),'canonical':esc(canonical),'alternates':alternates,'base':esc(self.base),'root':self.root,'home':self.path(lang),'database':self.path(lang,'database/'),'credits':self.path(lang,'docs/credits/'),'download':DOWNLOAD,'repo':REPO,'dbRepo':DB_REPO,'report':REPORT,'year':dt.date.today().year,'body':body,'heroAsset':esc(self.media['hero']['file']),'heroPlaceholder':'<span class="placeholder-label">{{placeholder}}</span>' if self.media['hero']['placeholder'] else '', 'appAsset':esc(self.media['app']), 'dlssOriginal':esc(self.media['dlss']['original']),'dlssUpscaled':esc(self.media['dlss']['upscaled']),'comparisonClass':'is-placeholder' if self.media['dlss']['placeholder'] else '', 'dlssPlaceholder':'<span class="placeholder-label">{{placeholder}}</span>' if self.media['dlss']['placeholder'] else '', 'config':safe_json(config),'schema':safe_json(schema),'languageOptions':lang_options,'pageClass':page,'extraHead':'<meta name="robots" content="noindex,follow">' if noindex else '',**ICONS}
        values['ogLocale']={'en':'en_US','es':'es_AR','ru':'ru_RU','zh':'zh_CN','ja':'ja_JP','ko':'ko_KR','pt':'pt_BR'}[lang]
        hero_concept=self.media['hero'].get('concept',False)
        dlss_concept=self.media['dlss'].get('concept',False)
        values.update(heroAlt='{{devicesConceptAlt}}' if hero_concept else '',
                      heroConceptNote='<span class="hero-concept-note">{{devicesConceptNote}}</span>' if hero_concept else '',
                      comparisonAlt='{{dlssConceptAlt}}' if dlss_concept else '',
                      comparisonLeft='{{conceptSoft}}' if dlss_concept else '{{dlssOff}}',
                      comparisonRight='{{conceptDetail}}' if dlss_concept else '{{dlssOn}}',
                      comparisonNote='{{dlssConceptNote}}' if dlss_concept else '{{demoNote}}')
        if hero_concept: values['heroPlaceholder']='<span class="placeholder-label">{{visualConcept}}</span>'
        if dlss_concept:
            values['comparisonClass']='is-concept'
            values['dlssPlaceholder']='<span class="placeholder-label">{{visualConcept}}</span>'
        if substitutions: values.update(substitutions)
        body=Template(body).safe_substitute(values)
        values['body']=self.translate(body,lang)
        result=self.translate(Template((HERE/'templates/layout.html').read_text()).substitute(values),lang)
        self.write((f'{lang}/' if lang!='en' else '')+route+'index.html',result)
        if not noindex: self.sitemap.append((canonical,lang,route))

    def home(self,lang):
        byid={g['id']:g for g in self.games}
        favorites=['red-dead-redemption-2','cyberpunk-2077','elden-ring','assetto-corsa','marvels-guardians-of-the-galaxy',
                   'metaphor-refantazio','naruto-shippuden-ultimate-ninja-storm-4','peak','ghostrunner','portal-2',
                   'alien-isolation','grand-theft-auto-v','warframe','hollow-knight']
        artwork=[]
        for id in favorites:
            if id not in byid: continue
            g=byid[id]; appid=g.get('steam_appid'); meta=catalog.metadata(self.catalog,appid,lang)
            custom=self.media['covers'].get(id)
            candidates=([f'{self.root}/static/{custom}'] if custom else [])
            if meta.get('header'): candidates.append(meta['header'])
            if appid: candidates.append(f'{catalog.CDN}/{appid}/header.jpg')
            candidates+=catalog.cover_candidates(appid,meta,root=self.root)
            candidates=list(dict.fromkeys(candidates))
            if not candidates: continue
            artwork.append(f'<div class="game-wall-tile game-art"><img class="game-cover" src="{esc(candidates[0])}" data-artwork data-fallbacks="{esc(safe_json(candidates[1:]))}" alt="" width="460" height="215" loading="lazy" decoding="async" draggable="false" referrerpolicy="no-referrer"></div>')
        rows=[]
        for i,(start,end) in enumerate([(0,5),(5,10),(10,14)]):
            if not artwork[start:end]: continue
            group='<div class="game-wall-group">'+''.join(artwork[start:end])+'</div>'
            # Equal-width copies give the CSS loop an exact quarter-track boundary.
            rows.append(f'<div class="game-wall-row row-{i+1}"><div class="game-wall-track">{group*4}</div></div>')
        game_wall=''.join(rows)
        faqs=''.join(f'<details class="faq-item"><summary>{{{{q{i}}}}}<span aria-hidden="true">＋</span></summary><p>{{{{a{i}}}}}</p></details>' for i in range(1,6))
        blocked_examples=[]
        for id in ['fortnite','valorant']:
            game=byid[id]
            if game['status']!='blocked-anticheat':
                raise ValueError(f'Update the homepage anti-cheat explanation: {id} is no longer blocked.')
            blocked_examples.append(f'<a class="compatibility-game" href="{self.path(lang,"games/"+id+"/")}"><span class="compatibility-game-name">{esc(game["title"])}</span><span class="status-pill blocked-anticheat"><i></i>{esc(self.locales[lang]["blocked-anticheat"])}</span><span class="compatibility-game-arrow" aria-hidden="true">↗</span></a>')
        dlss_lead,dlss_mac=self.locales[lang]['dlssTitle'].split('\n',1)
        self.render(lang,'',(HERE/'templates/home.html').read_text(),substitutions={'blockedGameExamples':''.join(blocked_examples),'blockedGamesLabel':esc(self.locales[lang]['blockedGamesLink'].format(count=self.counts['blocked-anticheat'])),'gameWall':game_wall,'faqs':faqs,'dlssHeadline':f'{esc(dlss_lead)}<br><span class="dlss-highlight">{esc(dlss_mac)}</span>','gamesHeadline':esc(self.locales[lang]['gamesTitle'].format(count=(len(self.games)//100)*100 or len(self.games))).replace('\n','<br>')})

    def database(self,lang,predictions=False):
        t=self.locales[lang]
        route='database/predictions/' if predictions else 'database/'
        labels=['all','likely','maybe','unlikely','blocked'] if predictions else ['all','verified-local','reported-upstream','communityStatus','blocked-anticheat','blocked-publisher']
        statuses=['all','likely','maybe','unlikely','blocked'] if predictions else ['all','verified-local','reported-upstream','community','blocked-anticheat','blocked-publisher']
        filters=''.join(f'<button class="filter {"active" if i==0 else ""}" data-filter="{s}" aria-pressed="{"true" if i==0 else "false"}">{esc(t[k])}</button>' for i,(k,s) in enumerate(zip(labels,statuses)))
        modes=[]
        for mode,path,key,count,active in [
            ('curated','database/','curatedGames',len(self.games),not predictions),
            ('predictions','database/predictions/','predictionsTitle',len(self.predictions),predictions)]:
            current=' aria-current="page"' if active else ''
            modes.append(f'<a class="database-mode {"active" if active else ""}" data-search-mode="{mode}" href="{self.path(lang,path)}"{current}><span>{esc(t[key])}</span><small>{count:,}</small></a>')
        modes=''.join(modes)
        stat_labels={'verified-local':'verified-local','reported-upstream':'reported-upstream','community':'communityStatus','blocked-anticheat':'blocked-anticheat','blocked-publisher':'blocked-publisher'}
        symbols={'verified-local':'✓','reported-upstream':'↗','community':'◎','blocked-anticheat':'⊘','blocked-publisher':'↗'}
        stats=''.join(f'<div class="db-stat {status}" data-stat-status="{status}"><dt><span class="stat-dot" aria-hidden="true"></span>{esc(t[key])}</dt><dd><span class="stat-number">{self.counts[status]}</span><span class="stat-symbol" aria-hidden="true">{symbols[status]}</span></dd></div>' for status,key in stat_labels.items())
        summary='' if predictions else '<section class="database-summary reveal" aria-labelledby="stats-title"><div class="stats-heading"><h2 id="stats-title">{{statsTitle}}</h2><p>'+esc(t['statsTotal'].format(count=len(self.games)))+'</p></div><dl class="database-stats">'+stats+'</dl></section>'
        links=''.join(f'<a href="{self.path(lang,"games/"+g["id"]+"/")}">{esc(g["title"])}</a>' for g in self.games)
        noscript='<p>{{searchRequiresJS}}</p>' if predictions else '<p>{{curatedNote}}</p><div class="noscript-games">'+links+'</div>'
        self.render(lang,route,(HERE/'templates/database.html').read_text(),title=f'{t["predictionsTitle"] if predictions else t["check"]} — Highball',desc=t['predictionNote'] if predictions else t['dbMeta'],page='database',noindex=predictions,search_mode='predictions' if predictions else 'curated',substitutions={
            'dbHeading':esc(t['predictionsHeading'] if predictions else t['dbTitle']),
            'dbIntro':esc(t['predictionNote'] if predictions else t['dbText']),
            'searchModes':modes,'statsSummary':summary,'searchAction':self.path(lang,route),
            'filters':filters,'searchNote':esc(t['predictionsEvidence'] if predictions else t['curatedNote']),
            'initialCount':len(self.predictions) if predictions else len(self.games),
            'initialGames':'' if predictions else ''.join(self.card(g,lang,i) for i,g in enumerate(self.games[:12])),
            'noscriptContent':noscript,'predictionDate':esc(self.derived.get('generated','—'))})

    def game(self,g,lang):
        t=self.locales[lang]
        id=g['id'];status=g['status'];label=t['communityStatus' if status=='community' else status]
        body=f'<article class="game-page section-shell"><a class="text-link back-link" href="$database">← {{{{back}}}}</a><div class="game-page-heading"><div><p class="eyebrow">HIGHBALL / {{{{check}}}}</p><h1>{esc(g["title"])}</h1><span class="status-pill {status}"><i></i>{esc(label)}</span></div><a class="button" href="$download">$apple {{{{download}}}}</a></div>'
        body+=self.overview(g,lang)
        if status=='blocked-anticheat': body+='<aside class="notice warning">{{a4}}</aside>'
        elif status=='blocked-publisher': body+='<aside class="notice warning"><strong>{{blocked-publisher}}</strong><p>{{publisherBlockNote}}</p></aside>'
        if g.get('nativeMac',{}).get('available'):
            body+='<aside class="notice"><strong>{{native}}</strong><p>{{nativeNote}}</p>' + f'<p lang="en">{esc(g["nativeMac"].get("note",""))}</p></aside>'
        body+='<div class="game-details"><section><h2>{{notes}}</h2><small class="muted">{{originalNotes}}</small>'
        body+=f'<p class="source-notes" lang="en">{esc(g.get("notes") or "—")}</p><h3>{{{{provenance}}}}</h3><p lang="en">{esc(g.get("provenance") or "—")}</p>'
        if self.reports.get(id):
            body+='<h3>{{reports}}</h3>'
            for r in self.reports[id][:8]:
                body+=f'<article class="report-item"><div><strong>{esc(r.get("chip") or "—")}</strong><span>{esc((r.get("date") or "")[:10])} · {esc(r.get("renderer") or "—")}</span></div><p lang="en">{esc(r.get("notes") or "—")}</p></article>'
        if g.get('rendererResults'):
            body+='<h3>{{renderer}}</h3><div class="renderer-results">'
            for name,verdict in g['rendererResults'].items():
                body+=f'<p><strong>{esc(name.upper())}</strong> <span lang="en">{esc(verdict if isinstance(verdict,str) else json.dumps(verdict,ensure_ascii=False))}</span></p>'
            body+='</div>'
        body+='</section><aside class="game-sidebar"><h3>{{evidence}}</h3><dl>'
        body+=f'<dt>{{{{lastTest}}}}</dt><dd>{esc(g["lastVerified"]) if g.get("lastVerified") else esc(t["unknownDate"])}</dd><dt>{{{{renderer}}}}</dt><dd>{esc(g.get("renderer") or "—").upper()}</dd>'
        if g.get('verified'):
            v=g['verified'];body+=f'<dt>{{{{hardware}}}}</dt><dd>{esc(v.get("chip","—"))}<br>macOS {esc(v.get("macos","—"))}</dd>'
        body+='</dl>'
        if id in self.recipes:
            body+=f'<div class="recipe-box"><p>✦ {{{{recipe}}}}</p><a class="text-link" href="{DB_REPO}/blob/main/{esc(self.recipes[id]["path"])}">{{{{recipeLink}}}} ↗</a></div>'
        body+=f'<a class="text-link" href="{DB_REPO}/blob/main/db/games/{esc(id)}.json">{{{{readSource}}}} ↗</a><a class="text-link" href="{REPORT}&amp;{esc(urlencode({"title":g["title"],"steam_appid":g.get("steam_appid") or ""}))}">{{{{report}}}} ↗</a></aside></div><p class="data-attribution">{{{{dataCredit}}}}</p></article>'
        self.render(lang,f'games/{id}/',body,title=f'{g["title"]} — {t["check"]} · Highball',desc=f'{g["title"]}: {label}. {t["dbMeta"]}',page='game')

    def overview(self,g,lang):
        meta=catalog.metadata(self.catalog,g.get('steam_appid'),lang)
        if not meta:return ''
        source_lang=meta.get('language','en')
        image=f'<div class="overview-image"><img src="{esc(meta["header"])}" alt="" width="920" height="430" decoding="async" data-optional-image referrerpolicy="no-referrer"></div>' if meta.get('header') else ''
        body='<section class="game-overview">'+image+'<div class="overview-copy"><p class="eyebrow">{{aboutGame}}</p>'
        if meta.get('genres'):
            body+='<div class="genre-tags" lang="'+esc(source_lang)+'">'+''.join(f'<span>{esc(genre)}</span>' for genre in meta['genres'])+'</div>'
        body+=f'<p class="store-description" lang="{esc(source_lang)}">{esc(meta.get("description",""))}</p>'
        if source_lang!=lang:body+='<small class="catalog-fallback">{{descriptionFallback}}</small>'
        body+='<dl class="store-facts">'
        if meta.get('developers'):body+=f'<div><dt>{{{{developer}}}}</dt><dd>{esc(", ".join(meta["developers"]))}</dd></div>'
        if meta.get('release'):body+=f'<div><dt>{{{{releaseDate}}}}</dt><dd lang="{esc(source_lang)}">{esc(meta["release"])}</dd></div>'
        body+=f'</dl><a class="text-link" href="{esc(meta["store_url"])}">{{{{viewSteam}}}} ↗</a></div></section>'
        if meta.get('screenshots'):
            body+='<section class="screenshots-section"><div class="screenshots-heading"><h2>{{screenshots}}</h2><span>STEAM ↗</span></div><div class="screenshot-gallery">'
            for i,shot in enumerate(meta['screenshots']):
                body+=f'<button type="button" class="screenshot-button" data-screenshot="{esc(shot["full"])}" aria-label="{esc(self.locales[lang]["openScreenshot"])} {i+1}"><img src="{esc(shot["thumbnail"])}" alt="" width="600" height="338" loading="lazy" decoding="async" data-optional-image referrerpolicy="no-referrer"><span aria-hidden="true">↗</span></button>'
            body+='</div><p class="media-credit">{{mediaCredit}}</p></section><dialog id="screenshot-dialog" class="screenshot-dialog" aria-label="{{screenshots}}"><button class="screenshot-close" aria-label="{{close}}">×</button><img class="lightbox-image" alt="{{screenshots}}" referrerpolicy="no-referrer"><div class="lightbox-controls"><button class="screenshot-prev" aria-label="{{previousImage}}">←</button><span class="screenshot-counter" role="status" aria-live="polite"></span><button class="screenshot-next" aria-label="{{nextImage}}">→</button></div></dialog>'
        else:body+='<p class="media-credit">{{mediaCredit}}</p>'
        return body

    def docs(self,lang):
        routes={'install':('step1','<h2>{{stepsTitle}}</h2><h3>01 · {{step1}}</h3><p>{{step1Text}}</p><h3>02 · {{step2}}</h3><p>{{step2Text}}</p><h3>03 · {{step3}}</h3><p>{{step3Text}}</p><aside class="notice">{{setupNote}}</aside><p>{{requirements}}</p><a class="button" href="$download">$apple {{download}}</a>'), 'anti-cheat':('q4','<p>{{a4}}</p><a class="button" href="$database">{{check}} ↗</a>'), 'credits':('credits','<p>{{sourceNote}}</p><p>{{dataCredit}}</p><ul><li><a href="https://www.winehq.org/">Wine ↗</a></li><li><a href="https://github.com/Gcenx">Gcenx ↗</a></li><li><a href="https://github.com/3Shain/dxmt">DXMT ↗</a></li><li><a href="https://github.com/doitsujin/dxvk">DXVK ↗</a></li><li><a href="https://developer.apple.com/games/game-porting-toolkit/">Apple Game Porting Toolkit ↗</a></li><li><a href="$dbRepo">Highball DB · CC0 ↗</a></li><li><a href="https://www.protondb.com/">ProtonDB ↗</a> · <a href="https://opendatacommons.org/licenses/odbl/1-0/">ODbL-1.0 ↗</a></li><li><a href="https://areweanticheatyet.com/">AreWeAntiCheatYet · MIT ↗</a></li></ul><a class="button button-outline" href="$repo">{{github}} ↗</a>'), 'data':('dataLink','<p>{{curatedNote}}</p><p>{{predictionNote}}</p><p>{{dataCredit}}</p><a class="text-link" href="$root/data/games.json">CC0 JSON ↗</a><a class="text-link" href="$root/data/predictions.json">ODbL JSON ↗</a>')}
        for route,(key,content) in routes.items():
            body='<article class="doc-page section-shell"><a class="text-link" href="$home">← Highball</a><p class="eyebrow">HIGHBALL</p><h1>{{'+key+'}}</h1>'+content+'</article>'
            self.render(lang,f'docs/{route}/',body,title=self.locales[lang][key]+' — Highball',page='docs')

    def build(self):
        # Only clear an explicitly generated directory, never source or database paths.
        if self.out in [HERE,HERE.parent,Path('/')] or HERE.is_relative_to(self.out):
            raise ValueError('Output directory must not contain website sources.')
        if self.out.exists():
            marker=self.out/'.highball-build'
            if any(self.out.iterdir()) and not marker.exists(): raise ValueError('Refusing to replace unmarked output. Choose an empty --out directory.')
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        (self.out/'.highball-build').write_text('generated by build.py\n')
        shutil.copytree(HERE/'static',self.out/'static')
        self.write('.nojekyll','')
        shutil.copyfile(HERE/'static/favicon.ico',self.out/'favicon.ico')
        curated=[]
        for game in self.games:
            # Keep the original public JSON fields stable; newer fields are additive.
            curated.append({**game,'renderer':game.get('renderer'),
                'lastVerified':game.get('lastVerified'),'provenance':game.get('provenance'),
                'notes':game.get('notes'),'anticheat':game.get('anticheat'),
                'cover':self.media['covers'].get(game['id']),
                'reports':len(self.reports.get(game['id'],[])),'recipe':game['id'] in self.recipes,
                'url':f'{self.base}/games/{game["id"]}/'})
        status_meanings={
            'verified-local':'Tested by Highball on real Apple Silicon hardware.',
            'reported-upstream':'Named in upstream release notes as working or fixed; not yet verified by Highball.',
            'community':'Community consensus; unverified by Highball.',
            'blocked-anticheat':'Kernel anti-cheat prevents compatibility-layer play.',
            'blocked-publisher':'Publisher restrictions prevent compatibility-layer play.',
        }
        self.write('data/games.json',safe_json({
            'license':'CC0-1.0','license_url':'https://creativecommons.org/publicdomain/zero/1.0/',
            'source':DB_REPO,'note':'Curated compatibility data for running Windows games on Apple Silicon. Each entry carries its provenance. anticheat fields are derived from AreWeAntiCheatYet (MIT).',
            'generated':dt.date.today().isoformat(),'status_meanings':status_meanings,
            'count':len(curated),'games':curated}))
        prediction_labels={'likely':('Likely playable','good'),'maybe':('Maybe','warn'),'unlikely':('Unlikely','bad'),'blocked':('Blocked','bad')}
        prediction_index={str(game['steam_appid']):{
            't':game['title'],'s':game['id'],
            'p':prediction_labels.get(game['prediction'],prediction_labels['maybe'])[0],
            'c':prediction_labels.get(game['prediction'],prediction_labels['maybe'])[1],
            'pt':game.get('protonTier') or '?','n':game.get('reports',0),
        } for game in self.predictions}
        self.write('data/predictions.json',safe_json({
            'license':'ODbL-1.0','license_url':'https://opendatacommons.org/licenses/odbl/1-0/',
            'source':'Derived from ProtonDB community reports (https://github.com/bdefore/protondb-data), crossed with AreWeAntiCheatYet data (MIT).',
            'note':'Proton describes Linux, not macOS. These are odds, not verdicts, and no Mac verification stands behind them.',
            'generated':dt.date.today().isoformat(),'dataset_generated':self.derived.get('generated'),
            'count':len(self.predictions),'games':prediction_index,'items':self.predictions}))
        self.write('data/anticheat.json',safe_json(self.anticheat))
        for lang in LANGUAGES:
            entries={appid:catalog.metadata(self.catalog,appid,lang) for appid in self.catalog['games']}
            self.write(f'data/catalog/{lang}.json',safe_json({'source':'Steam store','rights':'Store metadata and artwork retain their respective rights; not part of the CC0 compatibility database.','games':entries}))
        for lang in LANGUAGES:
            self.home(lang);self.database(lang);self.database(lang,predictions=True);self.docs(lang)
            for g in self.games: self.game(g,lang)
        # Preserve old prediction URLs with noindex static redirects into localized search.
        for p in self.predictions:
            url=self.path('en','database/predictions/')+'?'+urlencode({'q':p['title'],'game':p['steam_appid']})
            self.write(f'games/{p["id"]}/index.html',f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,follow"><meta http-equiv="refresh" content="0;url={esc(url)}"><title>{esc(p["title"])} — Highball</title></head><body><a href="{esc(url)}">{esc(p["title"])} — Check your game</a></body></html>')
        for f in (HERE/'content').rglob('*.html'):
            relative=str(f.relative_to(HERE/'content').with_suffix(''))
            route='vs/'+f.stem+'/' if relative.startswith('vs/') else 'docs/'+f.stem+'/'
            if (self.out/route/'index.html').exists(): continue
            dest=self.path('en')+('#features' if route.startswith('vs') else '#start')
            self.write(route+'index.html',f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,follow"><meta http-equiv="refresh" content="0;url={dest}"><title>Highball</title></head><body><a href="{dest}">Highball</a></body></html>')
        entries=[]
        for url,lang,route in self.sitemap:
            alternates=''.join(f'<xhtml:link rel="alternate" hreflang="{code}" href="{esc(self.base+"/"+("" if code=="en" else code+"/")+route)}"/>' for code in LANGUAGES)
            entries.append(f'<url><loc>{esc(url)}</loc>{alternates}</url>')
        self.write('sitemap.xml','<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'+''.join(entries)+'</urlset>')
        self.write('robots.txt',f'User-agent: *\nAllow: /\nSitemap: {self.base}/sitemap.xml\n')
        if not self.root: self.write('CNAME',urlsplit(self.base).hostname+'\n')
        body='<section class="doc-page section-shell"><p class="eyebrow">404 / HIGHBALL</p><h1>{{notFound}}</h1><p>{{notFoundText}}</p><a class="button" href="$home">{{home}} ↗</a></section>'
        self.render('en','404/',body,title='404 — Highball',page='docs',noindex=True)
        shutil.copyfile(self.out/'404/index.html',self.out/'404.html')
        print(f'Built {len(LANGUAGES)} languages, {len(self.games)} curated games, {len(self.predictions):,} searchable predictions → {self.out}')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default=str(HERE.parent/'highball-db'))
    parser.add_argument('--out',default=str(HERE/'dist'))
    parser.add_argument('--base',default='https://gethighball.com')
    parser.add_argument('--catalog',default=str(HERE/'.cache/steam.json'),help='Optional cached Steam metadata; no network requests during rendering.')
    args=parser.parse_args()
    Builder(args).build()
