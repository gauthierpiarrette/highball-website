#!/usr/bin/env python3
"""Refresh the website's cached Steam catalog without changing compatibility data."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import catalog

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--db',default=str(Path(__file__).resolve().parents[2]/'highball-db'))
p.add_argument('--cache',default=str(Path(__file__).resolve().parents[1]/'.cache/steam.json'))
p.add_argument('--languages',default='en,es,ru,zh,ja,ko,pt')
p.add_argument('--localized-limit',type=int,default=24,help='Translate this many featured/first games; 0 translates all curated games.')
p.add_argument('--limit',type=int,help='Limit curated games for a small refresh.')
p.add_argument('--max-age',type=int,default=14)
p.add_argument('--force',action='store_true')
a=p.parse_args();languages=a.languages.split(',')
if any(lang not in catalog.STEAM_LANGUAGES for lang in languages):p.error('Unsupported language')
games=[json.loads(f.read_text()) for f in sorted((Path(a.db)/'db/games').glob('*.json'))]
if not games:p.error('No compatibility games found; check --db')
order={'verified-local':0,'reported-upstream':1,'community':2,'blocked-anticheat':3}
priority={'red-dead-redemption-2','cyberpunk-2077','portal-2','elden-ring'}
games.sort(key=lambda g:(0 if g['id'] in priority else 1,order.get(g['status'],9),g['title'].casefold()))
if a.limit:games=games[:a.limit]
catalog.sync(games,a.cache,languages,a.localized_limit,a.max_age,a.force)
