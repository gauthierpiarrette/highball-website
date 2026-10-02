# Highball website

A completely rebuilt, consumer-focused website for Highball: Windows games on Apple Silicon, Steam and Epic libraries, DLSS via MetalFX in supported configurations, and prominent open-source/community links.

Everything builds to static files for GitHub Pages. No npm install, framework, backend, external fonts, tracking, or runtime API is required. Python 3.9+ builds it; a modern browser runs the interactions.

## Run locally

The website is in `/Users/matias/Documents/Coding/highball-website`. The separate compatibility database is in `/Users/matias/Documents/Coding/highball-db`.

```sh
cd /Users/matias/Documents/Coding/highball-website
# Optional first-time metadata enrichment (subsequent builds can stay offline):
python3 scripts/sync-steam.py
python3 build.py
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Open <http://127.0.0.1:8000/> or <http://127.0.0.1:8000/es/>. After editing sources, rebuild and reload the browser.

For another checkout, clone the database alongside this repository:

```sh
git clone https://github.com/gauthierpiarrette/highball-db.git ../highball-db
python3 build.py --db ../highball-db
```

## Editing the template

- `templates/home.html`: landing page structure.
- `templates/layout.html`: navigation, footer, metadata.
- `templates/database.html`: game search and prediction dialog.
- `static/site.css`: responsive design and animation.
- `static/site.js`: search, filters, language switching, motion, visual slider and off-screen animation pausing.
- `locales/*.json`: EN, ES, RU, ZH (Simplified Chinese), JA, KO and PT. Every locale must contain the same keys; incomplete translations fail the build. Spanish uses an Argentine voice; Portuguese uses Brazilian phrasing.
- `media.json`: image replacements, without touching page markup.
- `build.py`: data integration, curated game pages and static SEO output.
- `catalog.py` and `scripts/sync-steam.py`: optional Steam store enrichment and cached refresh.
- `.cache/steam.json`: local cached store metadata (ignored by Git).

The maintainer-authored `content/first-game.html` and `content/troubleshooting.html` guides are published as English-only pages and linked from the footer. Other cloned-site `content/` fragments remain source/reference and redirect to relevant redesigned sections; the new site does not use the old `static/style.css`. The logo and favicon assets are reused from the original repository. The actual app screenshot is the reference for the AI-generated Mac device hero, used as a darkened full-width background behind the headline and buttons. The fantasy DLSS illustration is labelled Visual concept in every language; the sharpness slider is illustrative, not measured DLSS output. Generation prompts and provenance are recorded in `IMAGE-PROMPTS.md`. Publisher blocks such as World of Warships are labelled separately from kernel anti-cheat blocks. The database treats both as compatibility blockers but records different reasons. Game cards automatically use Steam artwork when an app ID is available, with abstract placeholders as a fallback.

## Add real images

Put your screenshots/covers inside `static/media/`, then edit `media.json`. Paths are relative to `static/`:

```json
{
  "hero": {"file": "media/your-gameplay.webp", "placeholder": false, "concept": false},
  "app": "app.jpg",
  "dlss": {
    "original": "media/dlss-off.webp",
    "upscaled": "media/dlss-on.webp",
    "placeholder": false,
    "concept": false
  },
  "covers": {
    "red-dead-redemption-2": "media/rdr2-cover.webp",
    "cyberpunk-2077": "media/cyberpunk-cover.webp",
    "portal-2": null,
    "elden-ring": null
  }
}
```

Use wide gameplay images (roughly 16:9), portrait game covers (roughly 3:4), and WebP/AVIF where practical. Add any curated game's database `id` to `covers` to replace its placeholder everywhere. Null/missing covers use Steam artwork where available, then the abstract placeholder. Custom images always take priority. Missing configured files fail the build. Set `concept` to false when replacing the generated artwork with real captures. This removes the concept badge, device caption, concept comparison labels and softening filter. Both DLSS images should show the same scene and framing. The comparison is illustrative and does not claim measured performance. When real captures arrive, update `demoNote` in the locale files as appropriate. The generated Mac hero and fantasy illustration are optimized JPEGs in `static/media/mac-devices-concept.jpg` and `static/media/fantasy-concept.jpg`.

## Animated game artwork

The homepage displays 14 games as three decorative rows of landscape artwork. Equal-width duplicate groups loop continuously in alternating directions, with no game names, status labels, links or selection controls on the artwork. The heading, database link and search bar remain; submitting the search opens the localized database with the query applied. Artwork uses cached Steam headers, honors custom covers, and falls back to the existing cover candidates. Animation pauses off-screen and in hidden tabs; reduced-motion preferences show a static wall. Change the `favorites` list in `Builder.home` to choose different games. The interactive compatibility database remains separate. A prominent anti-cheat section follows the artwork wall, explaining why Fortnite and Valorant cannot run through Highball, linking their curated evidence and the blocked-game filter. Its blocked-game total comes from the database. The build requires the named examples to remain classified as blocked, so a changed verdict prompts a copy update.

## Compatibility database

`highball-db` is the only compatibility source. The build reads:

- `db/games/*.json`: curated verdicts, notes, renderer data, native Mac availability and verification metadata.
- `db/reports/*.jsonl`: player reports.
- `recipes/*/*.json`: recommended game fixes, linked to their original source.
- `db/derived/derived.json`: ProtonDB predictions.
- `db/anticheat.json`: anti-cheat information.

The database page shows five compatibility totals computed from the curated entries: tested on Mac, upstream reports, community reports, anti-cheat blocks, and publisher blocks. These static totals remain independent of the current search/filter and exclude predictions. The overview is translated into all seven languages and displayed in a responsive grid.

Curated results always take precedence over predictions by Steam ID and title. Mac anti-cheat blocks override optimistic predictions. Curated search at `/database/` only loads the curated dataset and filters tested games, upstream reports, community reports, anti-cheat blocks and publisher blocks. Predictions have their own search at `/database/predictions/`, with likelihood filters and a prominent Linux-data explanation. Switching collections preserves the search query. Both searches run locally using separate generated JSON files; one dataset being unavailable does not prevent the other from loading. Artwork loads lazily from Steam’s CDN; the browser never queries the Steam store API. Compatibility JSON exports do not include Steam metadata. The UI distinguishes actual Mac tests, upstream reports, community reports, anti-cheat blocks, publisher blocks and predictions. Source notes remain in their original language, explicitly labelled, to avoid changing compatibility evidence through translation.

Curated games have static pages in every language. Prediction searches in all seven languages are `noindex,follow` and excluded from the sitemap. Predictions open a localized dialog. An entry graduates to an indexed game page when it is curated in highball-db; curated entries incorporate their Highball reports and recipes. Pure predictions never generate indexable pages. Legacy prediction URLs redirect to the matching search/detail state with `noindex,follow` and remain outside the sitemap. Search still exposes curated game links when JavaScript is disabled; full search and predictions need JavaScript.

To refresh your local data:

```sh
git -C ../highball-db pull --ff-only
python3 build.py
```

## Languages and SEO

English is the default static root (`/`). Other languages use `/es/`, `/ru/`, `/zh/`, `/ja/`, `/ko/`, `/pt/`; the database and curated game routes exist under each locale. Every localized indexed page has a canonical, hreflang alternatives, an x-default link, translated metadata, HTML language, and sitemap entry. The English-only first-game and troubleshooting guides have English canonicals and stay outside the localized sitemap alternates. Marketing copy exists in the HTML, not only in JavaScript.

Only a visit to the English home can automatically redirect. The detector checks the saved manual preference, then the browser's language list. An explicit localized URL is respected. Unsupported languages stay English; recognised crawlers receive English. Manual preferences survive visits, and language switching preserves the page, search and hash. The English root remains fully usable with JavaScript or storage disabled.

## Checks

```sh
python3 scripts/check.py
python3 -m unittest discover -s tests
node scripts/check-language.mjs
node --check static/site.js
```

The static check validates localized and English-only guide pages, source-data counts, deduplication, internal links/assets, translation markers, canonicals, hreflang and exclusion of predictions from the sitemap. The small Node check verifies language detection, saved preferences, crawler handling, explicit language routes and repository subpaths. Node is only needed for this check, not building or hosting the website.

## GitHub Pages

A prepared `.github/workflows/deploy.yml` builds from the separate database, restores the Steam catalog cache, refreshes stale store metadata, validates the output and uploads `dist/`. It retains the database update dispatch and hourly refresh. All resources are static and `.nojekyll` is generated.

Custom domain build (default):

```sh
python3 build.py --base https://gethighball.com
```

Repository subpath build:

```sh
python3 build.py --base https://gauthierpiarrette.github.io/highball-website --out dist-pages
python3 scripts/check.py --out dist-pages --base https://gauthierpiarrette.github.io/highball-website
```

The workflow reads the real base URL from GitHub Pages configuration. Subpath builds prefix navigation, assets, data fetches, redirects and language routes; they omit CNAME. Domain-root builds generate CNAME. Nothing has been pushed or deployed as part of the local redesign.

`dist/` and `dist-pages/` are generated files. Output directories have a marker; the builder refuses to clear unmarked nonempty directories or paths containing its sources.

## Licensing

Website code/content: GPL-3.0. Curated database: CC0-1.0. ProtonDB-derived predictions: ODbL-1.0. Anti-cheat data: AreWeAntiCheatYet, MIT. Data exports retain license/attribution metadata and the site links the sources. Steam store descriptions, artwork and screenshots retain their respective rights and are attributed to Steam/publishers. They are exported separately in `data/catalog/<language>.json`, outside the CC0 compatibility data. Space Grotesk is bundled locally under SIL Open Font License; see `static/media/SPACE-GROTESK-LICENSE.txt`.

The app's other components keep their respective licenses. DLSS marketing refers specifically to the app's DLSS-to-MetalFX support through compatible DXMT/D3DMetal configurations, not universal NVIDIA feature support.

## Steam catalog enrichment

Game cards attempt a portrait library cover, a standard library cover, the cached Steam header, and a standard store header, in that order. A custom cover in `media.json` is always first. If every image fails, the original artwork remains visible. Images load lazily, and no image files are downloaded into the source repository.

Cached game pages show a plain-text store description, genre tags, developer, release date, a Steam link, and up to six store screenshots. Screenshots open in an accessible dialog with previous/next controls, arrow-key navigation and Escape to close. These are publisher/store screenshots and do not establish Mac compatibility or measured performance.

```sh
python3 scripts/sync-steam.py
python3 build.py
```

The refresh uses Steam's public, undocumented store endpoint without an API key. It fetches English metadata for curated games with Steam IDs and localized data for the first 24 featured/tested games in ES, RU, ZH, JA, KO and PT. This bounded default keeps an initial refresh manageable. Other entries fall back to English with a visible notice. Games without Steam IDs keep their compatibility details and custom/placeholder imagery. Predicted games get lazy Steam artwork and a store link without making 12,000 metadata requests.

To localize the whole curated catalog:

```sh
python3 scripts/sync-steam.py --localized-limit 0
```

Useful flags: `--languages en,es`, `--limit 12`, `--max-age 14`, `--force`, `--cache PATH`, and `--db PATH`. The builder can read another cache via `python3 build.py --catalog PATH`. A missing cache is valid and produces the original compatibility site with automatic cover URLs; normal builds make no external API requests.

The fetcher spaces requests, retains existing data on failures, stores partial progress after small batches, and stops on HTTP 429. A cooldown is persisted, respecting longer Retry-After values where provided. Run it again after the cooldown to resume missing entries. Store entries unavailable in the chosen region are retried after one day; successful entries are refreshed after 14 days. The workflow caches progress between runs, so an interrupted or throttled refresh can resume without requesting fresh entries again.

```sh
python3 -m unittest discover -s tests
```

Tests cover plain-text sanitization, provider-ID validation, trusted image hosts, translated metadata fallback, custom artwork priority, offline builds, network failures, refresh expiry and persisted rate-limit cooldowns.
