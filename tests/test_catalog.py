import argparse
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import catalog
import build

class CatalogTests(unittest.TestCase):
    def fixture(self):
        return {'steam_appid':620,'name':'Portal 2','short_description':'A <b>puzzle</b> game &amp; a $20 adventure. <script>bad()</script>','header_image':'https://shared.akamai.steamstatic.com/steam/apps/620/header.jpg','genres':[{'description':'Adventure'}],'developers':['Valve'],'release_date':{'date':'Apr 18, 2011'},'screenshots':[{'path_full':'https://shared.fastly.steamstatic.com/full.jpg','path_thumbnail':'https://shared.fastly.steamstatic.com/thumb.jpg'}]}
    def test_description_is_plain_text_with_entities_decoded(self):
        record=catalog.normalize('620','en',self.fixture())
        self.assertEqual(record['description'],'A puzzle game & a $20 adventure.')
    def test_mismatched_steam_id_is_rejected(self):
        with self.assertRaises(ValueError):catalog.normalize('621','en',self.fixture())
    def test_untrusted_image_sources_are_rejected(self):
        for url in ['javascript:alert(1)','https://steamstatic.com.evil.test/picture.jpg','http://steamstatic.com/a.jpg','https://me@steamstatic.com/a.jpg']:
            self.assertIsNone(catalog.image_url(url))
    def test_localized_metadata_falls_back_to_english(self):
        cache={'games':{'620':{'en':{'description':'English'},'es':{'description':'Español'}}}}
        self.assertEqual(catalog.metadata(cache,620,'es')['description'],'Español')
        self.assertEqual(catalog.metadata(cache,620,'ja')['description'],'English')
        self.assertEqual(catalog.metadata(cache,None,'ja'),{})
    def test_custom_image_takes_priority_and_missing_art_has_steam_fallbacks(self):
        urls=catalog.cover_candidates(620,{'header':'https://shared.fastly.steamstatic.com/real.jpg'},'media/mine.webp','/highball-website')
        self.assertEqual(urls[0],'/highball-website/static/media/mine.webp')
        self.assertTrue(urls[1].endswith('/620/library_600x900_2x.jpg'))
        self.assertIn('https://shared.fastly.steamstatic.com/real.jpg',urls)
        self.assertEqual(catalog.cover_candidates(None),[])
    def test_network_failure_keeps_cached_details(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'steam.json';record=catalog.normalize('620','en',self.fixture())
            record['fetched_at']='2020-01-01T00:00:00+00:00';catalog.save_cache(path,{'version':1,'games':{'620':{'en':record}}})
            with patch('catalog.fetch',side_effect=OSError('offline')):
                result=catalog.sync([{'id':'portal-2','steam_appid':620}],path,force=True,interval=0)
            self.assertEqual(result['failed'],1)
            self.assertEqual(catalog.read_cache(path)['games']['620']['en'],record)
    def test_fresh_catalog_does_not_hit_steam(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'steam.json';record=catalog.normalize('620','en',self.fixture())
            catalog.save_cache(path,{'version':1,'games':{'620':{'en':record}}})
            with patch('catalog.fetch') as fetch:
                catalog.sync([{'id':'portal-2','steam_appid':620}],path,interval=0)
                fetch.assert_not_called()
    def test_rate_limit_persists_cooldown_and_retains_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'steam.json'
            with patch('catalog.fetch',side_effect=catalog.RateLimited('slow down',600)):
                catalog.sync([{'id':'portal-2','steam_appid':620}],path,interval=0)
            self.assertGreater(dt.datetime.fromisoformat(catalog.read_cache(path)['not_before']),dt.datetime.now(dt.timezone.utc))
            with patch('catalog.fetch') as fetch:
                catalog.sync([{'id':'portal-2','steam_appid':620}],path,interval=0)
                fetch.assert_not_called()
    def test_build_without_metadata_is_offline_and_keeps_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            b=build.Builder(argparse.Namespace(out=directory,base='https://gethighball.com',db=build.HERE.parent/'highball-db',catalog=Path(directory)/'missing.json'))
            g=next(g for g in b.games if g['id']=='portal-2')
            self.assertEqual(b.overview(g,'en'),'')
            self.assertIn('library_600x900_2x.jpg',b.card(g,'en'))
            self.assertEqual(g['status'],'verified-local')
    def test_store_html_and_dollar_prices_render_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            b=build.Builder(argparse.Namespace(out=directory,base='https://gethighball.com',db=build.HERE.parent/'highball-db',catalog=Path(directory)/'missing.json'))
            b.catalog['games']['620']={'en':catalog.normalize('620','en',self.fixture())}
            g=next(g for g in b.games if g['id']=='portal-2');b.game(g,'en')
            page=(Path(directory)/'games/portal-2/index.html').read_text()
            self.assertIn('A puzzle game &amp; a $20 adventure.',page)
            self.assertNotIn('bad()',page)
            self.assertIn('data-screenshot=',page)
            self.assertEqual(g['status'],'verified-local')

if __name__=='__main__':unittest.main()
