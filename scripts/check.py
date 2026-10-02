#!/usr/bin/env python3
"""Validate generated routes, languages, source data, SEO and static assets."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, unquote
import xml.etree.ElementTree as ET

class Page(HTMLParser):
    def __init__(self,text):
        super().__init__(); self.links=[]; self.ids=set(); self.lang=None; self.h1=0; self.canonical=None; self.alternates=[]; self.scripts=[]; self.noindex=False; self.visible=[]; self.in_script=False
        self.feed(text)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='html': self.lang=attrs.get('lang')
        if tag=='h1': self.h1+=1
        if attrs.get('id'): self.ids.add(attrs['id'])
        if tag=='a' and attrs.get('href'): self.links.append(attrs['href'])
        if tag in ('img','script') and attrs.get('src'): self.links.append(attrs['src'])
        if tag=='link':
            if attrs.get('rel')=='stylesheet': self.links.append(attrs['href'])
            if attrs.get('rel')=='canonical': self.canonical=attrs.get('href')
            if attrs.get('rel')=='alternate': self.alternates.append((attrs['hreflang'],attrs['href']))
        if tag=='meta' and attrs.get('name')=='robots' and 'noindex' in attrs.get('content',''): self.noindex=True
        if tag=='script': self.in_script=True
    def handle_endtag(self,tag):
        if tag=='script': self.in_script=False
    def handle_data(self,data):
        if not self.in_script: self.visible.append(data)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',default='dist');p.add_argument('--db',default='../highball-db');p.add_argument('--base',default='https://gethighball.com');a=p.parse_args()
    out=Path(a.out).resolve();base=urlsplit(a.base.rstrip('/'));prefix=base.path.rstrip('/');langs=['en','es','ru','zh','ja','ko','pt']
    games=[json.loads(f.read_text()) for f in (Path(a.db)/'db/games').glob('*.json')]
    exported=json.loads((out/'data/games.json').read_text());predictions=json.loads((out/'data/predictions.json').read_text())
    prediction_items=predictions.get('items',list(predictions['games'].values()) if isinstance(predictions['games'],dict) else predictions['games'])
    assert len(games)==exported['count']==len(exported['games'])
    assert {g['id']:g['status'] for g in exported['games']}=={g['id']:g['status'] for g in games}, 'Store metadata changed a compatibility verdict'
    assert exported['license']=='CC0-1.0' and predictions['license']=='ODbL-1.0'
    assert {'license_url','note','status_meanings'} <= exported.keys(), 'Curated export lost legacy metadata'
    assert all('url' in g and 'provenance' in g for g in exported['games']), 'Curated export lost legacy game fields'
    assert isinstance(predictions['games'],dict) and all({'t','s','p','c','pt','n'} <= entry.keys() for entry in predictions['games'].values()), 'Prediction export changed its legacy app-id index'
    ids={str(g.get('steam_appid')) for g in games if g.get('steam_appid')};titles={g['title'].strip().casefold() for g in games}
    assert all(str(g['steam_appid']) not in ids and g['title'].strip().casefold() not in titles for g in prediction_items), 'Predictions shadow curated data'
    assert len({g['id'] for g in [*games,*prediction_items]})==len(games)+len(prediction_items), 'Slug collision'
    pages={}; checked_links=set()
    for lang in langs:
        for route in ['','database/','database/predictions/','docs/credits/', *[f'games/{g["id"]}/' for g in games]]:
            path=(('' if lang=='en' else lang+'/')+route+'index.html')
            text=(out/path).read_text();page=Page(text);pages[path]=page
            assert page.lang==lang,(path,'lang')
            assert page.h1==1,(path,'h1')
            assert page.canonical==a.base.rstrip('/')+'/'+('' if lang=='en' else lang+'/')+route,(path,'canonical')
            assert {code for code,url in page.alternates}==set(langs+['x-default']),(path,'hreflang')
            assert page.noindex == (route=='database/predictions/'),(path,'incorrect indexing policy')
            assert not re.search(r'\{\{?[a-zA-Z_-]+\}?\}', ''.join(page.visible)),(path,'unresolved translation')
            if route in ('database/','database/predictions/'):
                config=json.loads(re.search(r'<script id="site-config" type="application/json">(.*?)</script>',text,re.S)[1])
                prediction_mode=route=='database/predictions/'
                assert config['searchMode']==('predictions' if prediction_mode else 'curated'),(path,'search mode')
                assert set(re.findall(r'data-filter="([^"]+)"',text))==({'all','likely','maybe','unlikely','blocked'} if prediction_mode else {'all','verified-local','reported-upstream','community','blocked-anticheat','blocked-publisher'}),(path,'mixed search filters')
                assert ('data-stat-status=' in text) != prediction_mode,(path,'mixed curated statistics')
            if route=='':
                assert 'class="marquee"' not in text,(path,'removed scrolling strip')
            for link in page.links:
                parsed=urlsplit(link)
                if parsed.scheme or parsed.netloc:continue
                target=unquote(parsed.path)
                if not target:continue
                assert target.startswith(prefix+'/'),(path,'incorrect project base',link)
                target=target[len(prefix)+1:]
                key=(target,parsed.fragment)
                if key in checked_links:continue
                checked_links.add(key)
                file=out/target
                if target.endswith('/'):file=file/'index.html'
                assert file.exists(),(path,'broken internal link',link)
                if parsed.fragment and file.suffix=='.html':assert parsed.fragment in Page(file.read_text()).ids,(path,'missing anchor',link)
    for route in ['docs/first-game/','docs/troubleshooting/']:
        path=route+'index.html';text=(out/path).read_text();page=Page(text);pages[path]=page
        assert page.lang=='en' and page.h1==1,(path,'English-only guide structure')
        assert page.canonical==a.base.rstrip('/')+'/'+route,(path,'guide canonical')
        assert not page.alternates,(path,'English-only guide must not advertise untranslated alternates')
        assert not page.noindex,(path,'guide unexpectedly noindex')
        assert not re.search(r'\{\{?[a-zA-Z_-]+\}?\}', ''.join(page.visible)),(path,'unresolved guide template marker')
        for link in page.links:
            parsed=urlsplit(link)
            if parsed.scheme or parsed.netloc:continue
            target=unquote(parsed.path)
            if not target:continue
            assert target.startswith(prefix+'/'),(path,'incorrect project base',link)
            target=target[len(prefix)+1:]
            key=(target,parsed.fragment)
            if key in checked_links:continue
            checked_links.add(key)
            file=out/target
            if target.endswith('/'):file=file/'index.html'
            assert file.exists(),(path,'broken internal link',link)
            if parsed.fragment and file.suffix=='.html':assert parsed.fragment in Page(file.read_text()).ids,(path,'missing anchor',link)
    tree=ET.parse(out/'sitemap.xml');urls=tree.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url')
    for entry in urls:
        url=entry.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc').text
        path=urlsplit(url).path[len(prefix)+1:]+'index.html'
        text=(out/path).read_text();assert not Page(text).noindex,('noindex in sitemap',path)
    assert len(urls)==len(langs)*(len(games)+6)+2,('sitemap count',len(urls))
    for game in prediction_items:
        text=(out/f'games/{game["id"]}/index.html').read_text()
        assert '<meta name="robots" content="noindex,follow">' in text,('prediction indexed',game['id'])
        assert prefix+'/database/predictions/?' in text,('legacy prediction destination',game['id'])
    assert (out/'.nojekyll').exists()
    assert '/docs/first-game/' in (out/'llms.txt').read_text()
    for lang in langs:
        data=json.loads((out/f'data/catalog/{lang}.json').read_text())
        assert data['source']=='Steam store' and 'not part of the CC0' in data['rights']
        assert all('status' not in record and 'prediction' not in record for record in data['games'].values()), 'Store catalog includes compatibility claims'
    for css_asset in re.findall(r'url\([\'\"]?([^\)\'\"]+)',(out/'static/site.css').read_text()):
        assert (out/'static'/css_asset).exists(),('missing CSS asset',css_asset)
    print(f'OK: {len(pages)} localized pages, {len(checked_links)} internal links, {len(urls)} SEO routes; {len(games)} curated games + {predictions["count"]:,} distinct predictions.')
