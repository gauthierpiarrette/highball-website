"""Steam store enrichment kept separate from Highball's compatibility data.

The website reads this cache offline. Only sync() performs network requests.
"""
import datetime as dt
from html.parser import HTMLParser
import html
import json
from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit

STEAM_LANGUAGES={'en':'english','es':'spanish','ru':'russian','zh':'schinese','ja':'japanese','ko':'koreana','pt':'brazilian'}
CDN='https://shared.fastly.steamstatic.com/store_item_assets/steam/apps'
CACHE_VERSION=1

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.blocked=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.blocked+=1
        if tag in ('br','p','li'):self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.blocked=max(0,self.blocked-1)
        if tag in ('p','li'):self.parts.append(' ')
    def handle_data(self,value):
        if not self.blocked:self.parts.append(value)

def plain(value):
    parser=PlainText();parser.feed(str(value or ''))
    return ' '.join(html.unescape(''.join(parser.parts)).split())

def image_url(value):
    """Accept image sources from Steam's CDN, not arbitrary store HTML URLs."""
    value=str(value or '')
    parsed=urlsplit(value)
    host=parsed.hostname or ''
    if parsed.scheme=='https' and (host=='steamstatic.com' or host.endswith('.steamstatic.com')) and not parsed.username and not parsed.password:
        return value
    return None

def normalize(appid,lang,data):
    if str(data.get('steam_appid'))!=str(appid):raise ValueError('Steam returned a different app ID')
    screenshots=[]
    for shot in data.get('screenshots',[])[:6]:
        full=image_url(shot.get('path_full'));thumb=image_url(shot.get('path_thumbnail'))
        if full and thumb:screenshots.append({'full':full,'thumbnail':thumb})
    return {'appid':str(appid),'language':lang,'name':plain(data.get('name')),'description':plain(data.get('short_description')),'header':image_url(data.get('header_image')),'genres':[plain(g.get('description')) for g in data.get('genres',[]) if g.get('description')],'developers':[plain(d) for d in data.get('developers',[])],'release':plain(data.get('release_date',{}).get('date')),'screenshots':screenshots,'store_url':f'https://store.steampowered.com/app/{appid}/','fetched_at':dt.datetime.now(dt.timezone.utc).isoformat()}

def read_cache(path):
    path=Path(path)
    if not path.exists():return {'version':CACHE_VERSION,'source':'Steam store','games':{}}
    cache=json.loads(path.read_text(encoding='utf-8'))
    if cache.get('version')!=CACHE_VERSION or not isinstance(cache.get('games'),dict):raise ValueError(f'Invalid catalog cache: {path}')
    return cache

def save_cache(path,cache):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)

def metadata(cache,appid,lang='en'):
    if not appid:return {}
    versions=cache.get('games',{}).get(str(appid),{})
    return versions.get(lang) or versions.get('en') or {}

def cover_candidates(appid,meta=None,custom=None,root=''):
    candidates=[f'{root}/static/{custom}'] if custom else []
    if appid and str(appid).isdigit():
        base=f'{CDN}/{appid}'
        candidates.extend([f'{base}/library_600x900_2x.jpg',f'{base}/library_600x900.jpg'])
        if (meta or {}).get('header'):candidates.append(meta['header'])
        candidates.append(f'{base}/header.jpg')
    return list(dict.fromkeys(candidates))

def fresh(entry,days):
    if not entry.get('fetched_at'):return False
    try:stamp=dt.datetime.fromisoformat(entry['fetched_at'])
    except ValueError:return False
    return (dt.datetime.now(dt.timezone.utc)-stamp).total_seconds()<days*86400

class RateLimiter:
    def __init__(self,interval):self.interval=interval;self.next_request=0;self.lock=threading.Lock()
    def wait(self):
        with self.lock:
            delay=max(0,self.next_request-time.monotonic());self.next_request=max(time.monotonic(),self.next_request)+self.interval
        if delay:time.sleep(delay)

class RateLimited(Exception):
    def __init__(self,message,retry_after=300):
        super().__init__(message);self.retry_after=retry_after

def fetch(appid,lang,limiter):
    limiter.wait()
    url='https://store.steampowered.com/api/appdetails?'+urlencode({'appids':appid,'l':STEAM_LANGUAGES[lang],'cc':'us'})
    request=urllib.request.Request(url,headers={'User-Agent':'HighballWebsite/1.0 (+https://gethighball.com)','Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            payload=json.load(response).get(str(appid),{})
    except urllib.error.HTTPError as error:
        if error.code==429:
            try:retry_after=max(300,int(error.headers.get('Retry-After','300')))
            except (ValueError,AttributeError):retry_after=300
            raise RateLimited('Steam rate limit reached; cached data retained',retry_after) from error
        raise
    if not payload.get('success'):return None
    return normalize(appid,lang,payload['data'])

def sync(games,path,languages=('en',),localized_limit=24,max_age=14,force=False,interval=1.7,workers=2):
    cache=read_cache(path);negative=cache.setdefault('unavailable',{})
    if not_before := cache.get('not_before'):
        deadline=dt.datetime.fromisoformat(not_before)
        if deadline>dt.datetime.now(dt.timezone.utc):
            print('Steam cooldown active; using cached catalog. Retry after '+not_before,flush=True)
            return {'updated':0,'unavailable':0,'failed':0,'rate_limited':True}
        cache.pop('not_before',None)
    appids=list(dict.fromkeys(str(g['steam_appid']) for g in games if g.get('steam_appid')))
    priority={'red-dead-redemption-2','cyberpunk-2077','portal-2','elden-ring'}
    localized=list(dict.fromkeys(str(g['steam_appid']) for g in games if g.get('steam_appid') and g['id'] in priority))
    localized+= [appid for appid in appids if appid not in localized]
    if localized_limit:localized=localized[:localized_limit]
    tasks=[]
    for lang in languages:
        for appid in (appids if lang=='en' else localized):
            existing=cache['games'].get(appid,{}).get(lang,{})
            missing=negative.get(f'{appid}:{lang}',{})
            if not force and (fresh(existing,max_age) or fresh(missing,1)):continue
            tasks.append((appid,lang))
    limiter=RateLimiter(interval);stats={'updated':0,'unavailable':0,'failed':0,'cached':len(appids),'rate_limited':False}
    print(f'Steam catalog: {len(tasks)} requests queued, {len(appids)} curated Steam games; refreshing every {max_age} days.',flush=True)
    # Small bounded batches allow a rate limit to halt promptly without queueing thousands of requests.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for offset in range(0,len(tasks),12):
            batch={pool.submit(fetch,appid,lang,limiter):(appid,lang) for appid,lang in tasks[offset:offset+12]}
            for future in as_completed(batch):
                appid,lang=batch[future]
                try:
                    result=future.result()
                    if result:
                        cache['games'].setdefault(appid,{})[lang]=result
                        negative.pop(f'{appid}:{lang}',None);stats['updated']+=1
                    else:
                        negative[f'{appid}:{lang}']={'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat()};stats['unavailable']+=1
                except RateLimited as error:
                    stats['rate_limited']=True;stats['failed']+=1
                    cache['not_before']=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=error.retry_after)).isoformat()
                except (OSError,ValueError,KeyError):stats['failed']+=1
            save_cache(path,cache)
            completed=min(offset+12,len(tasks))
            if completed%60==0 or completed==len(tasks) or stats['rate_limited']:
                print(f'Steam catalog: {completed}/{len(tasks)} checked; {stats["updated"]} updated, {stats["unavailable"]} unavailable, {stats["failed"]} failed.',flush=True)
            if stats['rate_limited']:break
    print(f'Cached catalog: {len(cache["games"])} games. Previous metadata is retained on connection failures.',flush=True)
    return stats
