# Window Website Harvester (100,000 – 600,000+ URLs)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/FredTheFork/emailscraper/blob/main/notebooks/Window_Website_Harvester_Colab.ipynb)

A production-grade, resumable multi-source discovery engine built to collect **every single window, glazing, and glass business website on Earth** — deduplicated to clean root URLs (`https://example.co.uk`) and filtered so you get **only real window businesses** (never Microsoft Windows OS sites, Facebook/Yelp/Checkatrade directory pages, opticians, wineglass shops, or parked domains).

### Every Window Sub-Vertical Covered
| Sub-Vertical Tag | Businesses Captured |
|---|---|
| `double_triple_glazing` | Double glazing, triple glazing, secondary glazing, acoustic/thermal glazing, misted unit specialists |
| `upvc_vinyl` | uPVC / PVCu windows, vinyl windows, REHAU / VEKA / Liniar / Kömmerling / Deceuninck fabricators & installers |
| `timber_wood` | Timber windows, box & sliding sash windows, flush casement, hardwood, oak, Accoya, alu-clad, heritage joinery |
| `aluminium` | Aluminium/aluminum windows, bi-fold doors & windows, slimline sliding, thermally broken (AluK, Schüco, Reynaers, Cortizo, Origin, Kawneer) |
| `steel_crittall` | Steel windows, Crittall & Crittall-style, wrought iron, bronze & architectural metal fenestration |
| `glass_glaziers` | Glaziers, flat/float glass, toughened/tempered, laminated, fire-rated, sealed units (IGUs), glass merchants & processors |
| `manufacturers_suppliers` | Window manufacturers, trade fabricators, wholesale/supply-only, profile extruders, hardware, hinges, seals & gaskets |
| `installers_replacement` | Window installation, replacement windows, repair & restoration, impact/hurricane, storm, bay/bow & egress windows |
| `commercial_curtain_wall` | Commercial glazing, curtain walling, architectural & structural glazing, glass facades & shopfronts/storefronts |
| `skylights_conservatories` | Skylights, roof windows (VELUX/FAKRO), roof lanterns, walk-on rooflights, conservatories, orangeries & sunrooms |
| `stained_decorative_glass` | Stained glass windows, leaded lights, etched/bevelled architectural glass |
| `window_film_tinting` | Architectural solar-control, privacy, manifestation & security window film |
| *Optional flags* | `--include-treatments` (shutters & blinds), `--include-window-cleaning`, `--include-auto-glass` |

---

## 16 Built-In Discovery Sources (Free + Optional Turbo APIs)

All sources feed into a single **WAL-mode SQLite master database** (`data/window_websites.db`) with instant root-domain deduplication, cross-source confidence boosting, and automatic task checkpointing (stop anytime with `Ctrl+C` and resume right where you left off).

| Source ID | Cost | Estimated Yield | What It Searches |
|---|---|---|---|
| `overture` | **FREE ($0)** | **80k – 220k+ URLs** | **Overture Maps Foundation** (60M+ global business POIs from Meta, Microsoft & TomTom) queried anonymously on public S3 via DuckDB in minutes — captures even brand-named firms like `origin-global.com` or `smithjoinery.co.uk` |
| `commoncrawl_domains` | **FREE ($0)** | **100k – 250k+ URLs** | Streams **Common Crawl's 100M+ active global domain graph** (ranked by PageRank) in <10 MB RAM and classifies every window/glazing/glass domain across 15+ languages |
| `commoncrawl_cdx` | **FREE ($0)** | **30k – 120k+ URLs** | Queries Common Crawl's CDX index for `/double-glazing*`, `/upvc-windows*`, `/timber-windows*`, `/aluminium-windows*`, `/window-replacement*`, `/curtain-walling*`, etc. across 23+ TLDs |
| `osm` | **FREE ($0)** | **20k – 55k+ URLs** | **OpenStreetMap Overpass** global sweep across 50 countries (`craft=glazier`, `craft=window_construction`, `shop=glaziery`, `shop=windows`, industrial glass & manufacturers) with multi-mirror failover |
| `crtsh` | **FREE ($0)** | **30k – 90k+ URLs** | **Certificate Transparency SSL Logs** (`crt.sh`) across 150+ double-glazing, uPVC, sash, timber, aluminium, steel, glazier & skylight patterns — catches brand-new websites |
| `metasearch` | **FREE ($0)** | **30k – 150k+ URLs** | Combinatorial `{keyword} × {city/postcode}` sweep across **DuckDuckGo, Brave, Startpage (Google results), Yahoo (Bing results) & Mojeek** with zero API keys |
| `yellowpages` | **FREE ($0)** | **25k – 75k+ URLs** | **YellowPages.com** business website harvester across 500+ US cities × 13 window, vinyl, wood, metal, skylight & glazier categories |
| `playwright_gmaps` | **FREE ($0)** | **50k – 250k+ URLs** | **Direct Google Maps Chromium Browser Scraper** — handles UK/EU cookie banners, scrolls feeds to end-of-list, extracts direct business website buttons |
| `trade_directories` | **FREE ($0)** | **2k – 25k+ URLs** | Outbound member-website crawler for window/glass trade associations (GGF, BWF, CAB, Steel Window Assoc., NFRC, WDMA, NGA, AGWA, etc.) + any custom `--seed-file` |
| `companies_house` | **FREE Key** | **15k – 45k+ UK URLs** | Official **UK Companies House API** across SIC codes `43342` (Glazing), `25120` (Metal Windows), `22230` (uPVC), `16230` (Timber Joinery), `23110`/`23120` (Flat Glass) + automatic website resolver |
| `serper` / `serper_maps` | Paid API (2.5k free) | **150k – 500k+ URLs** | **Fastest & cheapest Google Maps + Google Search API** (`serper.dev`) across the full `{keyword} × {city/postcode}` matrix + FENSA/CERTASS/NFRC/REHAU/AluK queries |
| `google_places` | Paid API ($200/mo free credit) | **100k – 450k+ URLs** | **Official Google Maps Places API (New)** with **Adaptive Quadtree Bounding-Box Subdivision** — automatically splits saturated tiles into NW/NE/SW/SE quadrants so dense cities like London or NYC never stop at 60 results |
| `brave_api` | Paid API (free tier) | **50k – 250k+ URLs** | **Official Brave Search API** (independent global crawler, up to 200 results/query across 30+ countries) |
| `serpapi` | Paid API | **50k – 350k+ URLs** | **SerpApi** harvesting Google Maps, Google Organic, Bing & Bing Maps |
| `dataforseo` | Paid API | **150k – 550k+ URLs** | **DataForSEO** deep live Google Maps (up to 300 businesses per single request) & Google Organic |

---

## Option A: Run Directly in Google Colab (Zero Install, Auto-Saves to Google Drive)

1. Open [`notebooks/Window_Website_Harvester_Colab.ipynb`](notebooks/Window_Website_Harvester_Colab.ipynb) in [Google Colab](https://colab.research.google.com/) (click the **Open in Colab** badge at the top after merging to `main`, or upload the `.ipynb` file to Colab).
2. Click **Runtime → Run all**.
3. Your deduplicated database and exported URL files save straight to your Google Drive at `MyDrive/window_websites/output/`:
   - `urls.txt` — pure list of website URLs, one per line
   - `domains.txt` — pure root domains, one per line
   - `websites.csv` — full spreadsheet (`url`, `domain`, `business_name`, `categories`, `country`, `region`, `city`, `postcode`, `phone`, `confidence`, `sources`, `verified_status`, `page_title`)
   - `chunks/urls_part_001.txt`, `urls_part_002.txt`, ... — 50,000-URL batches ready for Google Sheets or downstream scrapers
   - `by_country/GB_urls.txt`, `US_urls.txt`, `AU_urls.txt`, `CA_urls.txt`, `DE_urls.txt`, ...
   - `by_category/double_triple_glazing_urls.txt`, `upvc_vinyl_urls.txt`, `timber_wood_urls.txt`, `aluminium_urls.txt`, `steel_crittall_urls.txt`, `glass_glaziers_urls.txt`, `manufacturers_suppliers_urls.txt`, ...

---

## Option B: Run Locally, on a Cloud VM / VPS, or in Docker

### 1. Install
```bash
git clone https://github.com/FredTheFork/emailscraper.git
cd emailscraper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

*(Optional)* If you also want the free browser-based Google Maps scroller:
```bash
pip install playwright && playwright install chromium
```

### 2. Run a One-Command Harvest Preset

```bash
# Fastest 100% FREE run (~15–30 min, zero API keys -> ~120k–280k+ unique window URLs)
window-harvester run --preset free-fast --split-by-country --split-by-category

# Maximum 100% FREE run (every free dataset + DDG/Brave/Startpage/Bing/Mojeek + YellowPages -> ~180k–380k+ URLs)
window-harvester run --preset free-max --split-by-country --split-by-category

# Every single window, double glazing, uPVC, timber, sash, aluminium, steel & glass site in the UK
# (Sweeps 350+ UK cities/towns/London boroughs + all 121 UK postcode areas + datasets)
window-harvester run --preset uk-complete --split-by-category

# Exhaustive US all-50-states sweep (500+ cities)
window-harvester run --preset us-complete --split-by-category

# Full English-speaking world (UK, US, Canada, Australia, Ireland, New Zealand, South Africa)
window-harvester run --preset english-world --split-by-country --split-by-category

# Maximum planet-wide 500,000+ website harvest across 30+ countries & 15+ languages
window-harvester run --preset global-500k --split-by-country --split-by-category
```

### 3. Add API Keys to Sweep Google Maps, Google, Bing & Brave at Massive Speed (Optional)

```bash
cp .env.example .env
# Edit .env and paste any keys you want (SERPER_API_KEY, GOOGLE_PLACES_API_KEY, BRAVE_API_KEY,
# COMPANIES_HOUSE_API_KEY, DATAFORSEO_LOGIN/PASSWORD, SERPAPI_API_KEY, HARVESTER_PROXIES)

# Check which sources are ready
window-harvester sources

# Sweep Google Maps across UK cities + all ~2,000 UK postcode districts via Serper
window-harvester run --sources serper --countries GB --keyword-tier 3 --uk-postcode-districts

# Sweep Google Maps with Adaptive Quadtree bounding-box subdivision (never caps at 60 results!)
window-harvester run --sources google_places --countries GB,US,CA,AU,IE

# Sweep Google Maps for FREE using headless Chromium (resumable anytime!)
window-harvester run --sources playwright_gmaps --countries GB,US --max-tasks 2000

# Download all active UK window/glazing companies from Companies House & resolve their websites
window-harvester run --sources companies_house --countries GB
```

### 4. Verify Live Websites & Remove Dead/Parked Domains

```bash
# Checks 150 websites simultaneously (~30k–60k domains/hour), detects parked domains,
# confirms live window/glazing HTML content, enriches <title>, and upgrades sub-categories:
window-harvester verify --concurrency 150 --limit 200000

# Export only 100% HTTP-verified live window websites
window-harvester export --verified-only --split-by-country --split-by-category
```

### 5. Useful Inspection & Utility Commands

```bash
# View total domains, breakdown by sub-vertical, top countries & sources
window-harvester stats

# Preview query matrix size for any country combination
window-harvester plan --countries GB,US,CA,AU,IE,NZ,DE,FR,NL,PL --keyword-tier 3 --geo-tier 3

# Export just a specific vertical or country (e.g. only UK timber & aluminium window sites)
window-harvester export --countries GB --categories timber_wood,aluminium --format txt --output output/uk_timber_alu

# Merge & deduplicate any external .txt or .csv list of URLs into your master database
window-harvester import-urls my_extra_list.csv

# Test how the classifier scores any URLs
window-harvester classify safestyle-windows.co.uk crittall-windows.com windows11tips.com sunglasshut.com

# Run with Docker (also compatible with Google Cloud Run Jobs)
docker build -t window-harvester .
docker run --rm -v "$(pwd)/data:/app/data" -v "$(pwd)/output:/app/output" --env-file .env window-harvester run --preset global-500k
```

---

## How the Precision Noise-Killer Works

Searching the internet for `"windows"` and `"glass"` normally returns huge amounts of junk. Every URL entering this engine passes through a 3-layer filter (`window_harvester/domains.py`, `window_harvester/classifier.py`, `window_harvester/verifier.py`):

1. **URL Unwrapping & Canonical Root Deduplication**: Unwraps Google/Bing/DuckDuckGo/Yahoo/Facebook redirect links, strips tracking paths/queries, handles international IDN domains, and collapses every URL to its exact registered domain (`eTLD+1`) so you never get duplicate pages from the same business.
2. **300+ Aggregator / Directory / Tech Domain Blocklist**: Automatically excludes Facebook, Instagram, LinkedIn, YouTube, Yelp, Yell, YellowPages, Checkatrade, TrustATrader, MyBuilder, Bark, Angi, HomeAdvisor, Houzz, BBB, Trustpilot, Glassdoor, Companies House, Amazon, eBay, Screwfix, Home Depot, Wikipedia, news sites, `.gov`/`.edu`, domain-parking hosts, and Microsoft/software portals.
3. **Fenestration vs. Noise Lexical & HTML Classifier**: Separates genuine window, glazing, frame, skylight, conservatory, and architectural glass businesses from Microsoft Windows (Windows 10/11/Server, drivers, keys, hosting, software), opticians/eyewear (`glasses`, sunglasses, contact lenses), drinkware/glassware/bottles, smoking glass, phone screen repair, fiberglass boats/pools, music/botanical conservatories, auto windscreens (unless `--include-auto-glass`), and window cleaners (unless `--include-window-cleaning`).

## Running the Test Suite

```bash
pytest -v
```
