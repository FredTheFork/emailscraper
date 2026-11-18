"""URL normalization, redirect unwrapping, eTLD+1 extraction, junk-domain blocking, and TLD country mapping."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import tldextract

# Offline-first extractor using tldextract's bundled Mozilla Public Suffix List snapshot
# (never blocks on a network download and never fails in offline/firewalled runners).
_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

# Search-engine & social redirect wrapper parameters that contain the real destination URL
_REDIRECT_HOSTS: dict[str, tuple[str, ...]] = {
    "google.com": ("q", "url", "adurl"),
    "google.co.uk": ("q", "url", "adurl"),
    "google.ca": ("q", "url", "adurl"),
    "google.com.au": ("q", "url", "adurl"),
    "bing.com": ("u", "r", "url"),
    "duckduckgo.com": ("uddg", "u"),
    "l.facebook.com": ("u",),
    "lm.facebook.com": ("u",),
    "facebook.com": ("u",),
    "l.instagram.com": ("u",),
    "yelp.com": ("url",),
    "yelp.co.uk": ("url",),
    "yell.com": ("url", "redirect"),
    "yellowpages.com": ("url", "dest"),
    "search.yahoo.com": ("RU", "u"),
    "r.search.yahoo.com": ("RU", "u"),
}

# Subdomains that indicate non-website infrastructure when harvesting from CT logs
_INFRA_SUBDOMAINS: frozenset[str] = frozenset(
    {
        "mail",
        "webmail",
        "smtp",
        "imap",
        "pop",
        "pop3",
        "mx",
        "mx1",
        "mx2",
        "autodiscover",
        "autoconfig",
        "cpanel",
        "whm",
        "webdisk",
        "cpcalendars",
        "cpcontacts",
        "plesk",
        "ns1",
        "ns2",
        "ns3",
        "ns4",
        "dns",
        "ftp",
        "sftp",
        "vpn",
        "remote",
        "citrix",
        "owa",
        "exchange",
        "api",
        "cdn",
        "static",
        "assets",
        "img",
        "images",
        "media",
        "staging",
        "dev",
        "test",
        "uat",
        "sandbox",
        "beta",
        "old",
        "backup",
        "admin",
        "portal",
        "intranet",
        "login",
        "sso",
        "auth",
        "status",
        "monitor",
        "grafana",
        "jenkins",
        "git",
        "gitlab",
    }
)

# Public suffixes that never belong to commercial window businesses
_BLOCKED_SUFFIXES: frozenset[str] = frozenset(
    {
        "gov",
        "gov.uk",
        "gov.au",
        "gov.nz",
        "gov.ie",
        "gov.za",
        "gov.in",
        "gov.sg",
        "gc.ca",
        "gouv.fr",
        "gob.es",
        "gov.it",
        "gov.pl",
        "mil",
        "mil.uk",
        "mod.uk",
        "edu",
        "ac.uk",
        "sch.uk",
        "edu.au",
        "ac.nz",
        "edu.sg",
        "ac.za",
        "nhs.uk",
        "police.uk",
        "parliament.uk",
        "int",
        "arpa",
        "onion",
        "invalid",
        "example",
        "test",
        "localhost",
        "local",
        "internal",
    }
)

# Second-level brand prefixes blocked across ALL TLDs (e.g. google.*, amazon.*, yelp.*)
_BLOCKED_SECOND_LEVEL_GLOBAL: frozenset[str] = frozenset(
    {
        "google",
        "amazon",
        "ebay",
        "yelp",
        "pinterest",
        "yahoo",
        "tripadvisor",
        "glassdoor",
        "indeed",
        "craigslist",
        "gumtree",
        "yellowpages",
        "houzz",
        "europages",
        "kompass",
        "infobel",
        "cylex",
        "hotfrog",
        "trustpilot",
        "wikipedia",
        "wikimedia",
        "microsoft",
        "nextdoor",
        "threebestrated",
        "groupon",
        "ikea",
    }
)

# Exact root domains of social networks, directories, review platforms, marketplaces,
# search engines, software/OS portals, news sites, website builders, and parked hosts.
BLOCKED_DOMAINS: frozenset[str] = frozenset(
    {
        # Social & messaging
        "facebook.com",
        "fb.com",
        "fb.me",
        "messenger.com",
        "instagram.com",
        "threads.net",
        "linkedin.com",
        "lnkd.in",
        "twitter.com",
        "x.com",
        "t.co",
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "reddit.com",
        "redd.it",
        "snapchat.com",
        "whatsapp.com",
        "wa.me",
        "telegram.org",
        "t.me",
        "discord.com",
        "discord.gg",
        "tumblr.com",
        "flickr.com",
        "vimeo.com",
        "dailymotion.com",
        "twitch.tv",
        "quora.com",
        "medium.com",
        "substack.com",
        "vk.com",
        "ok.ru",
        "weibo.com",
        "line.me",
        "wechat.com",
        "bsky.app",
        "mastodon.social",
        "linktr.ee",
        "bio.link",
        "beacons.ai",
        "bit.ly",
        "tinyurl.com",
        "ow.ly",
        "buff.ly",
        "rebrand.ly",
        "shorturl.at",
        "goo.gl",
        # Search engines & maps
        "bing.com",
        "duckduckgo.com",
        "brave.com",
        "startpage.com",
        "mojeek.com",
        "ecosia.org",
        "qwant.com",
        "yandex.com",
        "yandex.ru",
        "baidu.com",
        "naver.com",
        "ask.com",
        "aol.com",
        "msn.com",
        "mapquest.com",
        "waze.com",
        "openstreetmap.org",
        "foursquare.com",
        "here.com",
        "apple.com",
        "icloud.com",
        "gstatic.com",
        "googleapis.com",
        "googleusercontent.com",
        "g.page",
        # Microsoft Windows / Big Tech / Software download & forum sites
        "windows.com",
        "windows.net",
        "windowsphone.com",
        "windowsupdate.com",
        "live.com",
        "outlook.com",
        "office.com",
        "office365.com",
        "sharepoint.com",
        "azure.com",
        "skype.com",
        "xbox.com",
        "visualstudio.com",
        "dotnet.microsoft.com",
        "github.com",
        "github.io",
        "githubusercontent.com",
        "gitlab.com",
        "gitlab.io",
        "bitbucket.org",
        "sourceforge.net",
        "stackoverflow.com",
        "stackexchange.com",
        "superuser.com",
        "serverfault.com",
        "askubuntu.com",
        "npmjs.com",
        "pypi.org",
        "docker.com",
        "cloudflare.com",
        "amazonaws.com",
        "digitalocean.com",
        "heroku.com",
        "herokuapp.com",
        "netlify.app",
        "netlify.com",
        "vercel.app",
        "vercel.com",
        "pages.dev",
        "workers.dev",
        "web.app",
        "firebaseapp.com",
        "mozilla.org",
        "adobe.com",
        "oracle.com",
        "ibm.com",
        "sap.com",
        "salesforce.com",
        "hubspot.com",
        "zendesk.com",
        "dell.com",
        "hp.com",
        "lenovo.com",
        "asus.com",
        "acer.com",
        "msi.com",
        "samsung.com",
        "lg.com",
        "sony.com",
        "intel.com",
        "amd.com",
        "nvidia.com",
        "cisco.com",
        "vmware.com",
        "broadcom.com",
        "windowscentral.com",
        "windowslatest.com",
        "windowsreport.com",
        "thewindowsclub.com",
        "windowsforum.com",
        "tenforums.com",
        "elevenforums.com",
        "sevenforums.com",
        "eightforums.com",
        "bleepingcomputer.com",
        "neowin.net",
        "thurrott.com",
        "petri.com",
        "onmsft.com",
        "pureinfotech.com",
        "winaero.com",
        "nirsoft.net",
        "sysinternals.com",
        "howtogeek.com",
        "ghacks.net",
        "makeuseof.com",
        "lifewire.com",
        "digitaltrends.com",
        "cnet.com",
        "zdnet.com",
        "pcmag.com",
        "pcworld.com",
        "techradar.com",
        "tomshardware.com",
        "tomsguide.com",
        "anandtech.com",
        "theverge.com",
        "wired.com",
        "arstechnica.com",
        "engadget.com",
        "techcrunch.com",
        "mashable.com",
        "gizmodo.com",
        "slashdot.org",
        "xda-developers.com",
        "spiceworks.com",
        "softpedia.com",
        "filehippo.com",
        "uptodown.com",
        "softonic.com",
        "majorgeeks.com",
        "download.com",
        "ninite.com",
        "chocolatey.org",
        "winget.run",
        "alternativeto.net",
        "g2.com",
        "capterra.com",
        "getapp.com",
        "softwareadvice.com",
        "trustradius.com",
        "producthunt.com",
        # Business directories, trade review portals & lead aggregators
        "yell.com",
        "thomsonlocal.com",
        "scoot.co.uk",
        "192.com",
        "freeindex.co.uk",
        "cylex-uk.co.uk",
        "uksmallbusinessdirectory.co.uk",
        "thebestof.co.uk",
        "near.co.uk",
        "locallife.co.uk",
        "checkatrade.com",
        "trustatrader.com",
        "mybuilder.com",
        "ratedpeople.com",
        "bark.com",
        "trustmark.org.uk",
        "which.co.uk",
        "fensa.org.uk",
        "certass.co.uk",
        "ggf.org.uk",
        "doubleglazingnetwork.com",
        "greenmatch.co.uk",
        "quotatis.co.uk",
        "householdquotes.co.uk",
        "priceyourjob.co.uk",
        "jobquote.co.uk",
        "tradesmenprices.co.uk",
        "feefo.com",
        "reviews.io",
        "reviews.co.uk",
        "birdeye.com",
        "podium.com",
        "sitejabber.com",
        "bbb.org",
        "angi.com",
        "angieslist.com",
        "homeadvisor.com",
        "thumbtack.com",
        "porch.com",
        "networx.com",
        "buildzoom.com",
        "modernize.com",
        "homeguide.com",
        "expertise.com",
        "fixr.com",
        "improvenet.com",
        "craftjack.com",
        "taskrabbit.com",
        "homestars.com",
        "trustedpros.ca",
        "hipages.com.au",
        "serviceseeking.com.au",
        "oneflare.com.au",
        "productreview.com.au",
        "truelocal.com.au",
        "localsearch.com.au",
        "whitepages.com.au",
        "whitepages.com",
        "nocowboys.co.nz",
        "builderscrack.co.nz",
        "neighbourly.co.nz",
        "goldenpages.ie",
        "onlinetradesmen.ie",
        "snupit.co.za",
        "kandua.com",
        "brabys.com",
        "superpages.com",
        "dexknows.com",
        "manta.com",
        "local.com",
        "merchantcircle.com",
        "chamberofcommerce.com",
        "alignable.com",
        "showmelocal.com",
        "ezlocal.com",
        "brownbook.net",
        "tupalo.com",
        "cybo.com",
        "find-open.co.uk",
        "opening-times.co.uk",
        "opendi.co.uk",
        "opendi.us",
        "yalwa.co.uk",
        "misterwhat.co.uk",
        "118information.co.uk",
        "pagesjaunes.fr",
        "societe.com",
        "pappers.fr",
        "verif.com",
        "gelbeseiten.de",
        "dasoertliche.de",
        "dastelefonbuch.de",
        "11880.com",
        "golocal.de",
        "meinestadt.de",
        "wlw.de",
        "werzuwem.de",
        "my-hammer.de",
        "herold.at",
        "local.ch",
        "search.ch",
        "goudengids.nl",
        "detelefoongids.nl",
        "werkspot.nl",
        "oozo.nl",
        "pagesdor.be",
        "goudengids.be",
        "paginegialle.it",
        "paginebianche.it",
        "prontopro.it",
        "paginasamarillas.es",
        "habitissimo.es",
        "empresite.eleconomista.es",
        "einforma.com",
        "pai.pt",
        "panoramafirm.pl",
        "pkt.pl",
        "oferteo.pl",
        "aleo.com",
        "eniro.se",
        "hitta.se",
        "allabolag.se",
        "gulesider.no",
        "1881.no",
        "proff.no",
        "krak.dk",
        "degulesider.dk",
        "proff.dk",
        "fonecta.fi",
        "finder.fi",
        "firmy.cz",
        "zlatestranky.cz",
        "thomasnet.com",
        "macraesbluebook.com",
        "bluebook.com",
        "thebluebook.com",
        "sweets.construction.com",
        "archiproducts.com",
        "archiexpo.com",
        "specifier.com.au",
        "specifiedby.com",
        "ribaproductselector.com",
        "thenbs.com",
        # Company data / B2B contact brokers / job boards
        "dnb.com",
        "zoominfo.com",
        "apollo.io",
        "lusha.com",
        "rocketreach.co",
        "cognism.com",
        "leadiq.com",
        "hunter.io",
        "clearbit.com",
        "crunchbase.com",
        "pitchbook.com",
        "owler.com",
        "opencorporates.com",
        "northdata.com",
        "endole.co.uk",
        "companycheck.co.uk",
        "pomanda.com",
        "ukdata.com",
        "checkcompany.co.uk",
        "bizdb.co.uk",
        "duedil.com",
        "fullcircl.com",
        "creditsafe.com",
        "experian.co.uk",
        "experian.com",
        "equifax.com",
        "companieshouse.gov.uk",
        "service.gov.uk",
        "reed.co.uk",
        "totaljobs.com",
        "cv-library.co.uk",
        "monster.com",
        "monster.co.uk",
        "ziprecruiter.com",
        "careerbuilder.com",
        "simplyhired.com",
        "seek.com.au",
        "stepstone.de",
        # Marketplaces, big-box general retail & property portals
        "etsy.com",
        "alibaba.com",
        "aliexpress.com",
        "made-in-china.com",
        "indiamart.com",
        "tradeindia.com",
        "justdial.com",
        "sulekha.com",
        "globalsources.com",
        "dhgate.com",
        "temu.com",
        "wish.com",
        "wayfair.com",
        "wayfair.co.uk",
        "overstock.com",
        "walmart.com",
        "target.com",
        "costco.com",
        "costco.co.uk",
        "homedepot.com",
        "homedepot.ca",
        "lowes.com",
        "lowes.ca",
        "menards.com",
        "acehardware.com",
        "bunnings.com.au",
        "bunnings.co.nz",
        "mitre10.co.nz",
        "mitre10.com.au",
        "diy.com",
        "screwfix.com",
        "toolstation.com",
        "homebase.co.uk",
        "argos.co.uk",
        "tesco.com",
        "asda.com",
        "sainsburys.co.uk",
        "johnlewis.com",
        "dunelm.com",
        "therange.co.uk",
        "wilko.com",
        "leroymerlin.fr",
        "leroymerlin.es",
        "leroymerlin.it",
        "leroymerlin.pl",
        "castorama.fr",
        "castorama.pl",
        "bricodepot.fr",
        "obi.de",
        "bauhaus.info",
        "hornbach.de",
        "toom.de",
        "gamma.nl",
        "praxis.nl",
        "karwei.nl",
        "rightmove.co.uk",
        "zoopla.co.uk",
        "onthemarket.com",
        "zillow.com",
        "realtor.com",
        "redfin.com",
        "trulia.com",
        "realestate.com.au",
        "domain.com.au",
        "booking.com",
        "airbnb.com",
        "airbnb.co.uk",
        "expedia.com",
        # News, magazines, home blogs & encyclopedias
        "wikidata.org",
        "wiktionary.org",
        "wikihow.com",
        "archive.org",
        "britannica.com",
        "dictionary.com",
        "merriam-webster.com",
        "cambridge.org",
        "collinsdictionary.com",
        "bbc.co.uk",
        "bbc.com",
        "theguardian.com",
        "telegraph.co.uk",
        "thetimes.com",
        "thetimes.co.uk",
        "dailymail.co.uk",
        "independent.co.uk",
        "mirror.co.uk",
        "express.co.uk",
        "thesun.co.uk",
        "metro.co.uk",
        "standard.co.uk",
        "sky.com",
        "itv.com",
        "channel4.com",
        "nytimes.com",
        "washingtonpost.com",
        "wsj.com",
        "usatoday.com",
        "cnn.com",
        "foxnews.com",
        "nbcnews.com",
        "cbsnews.com",
        "abcnews.go.com",
        "reuters.com",
        "apnews.com",
        "bloomberg.com",
        "ft.com",
        "forbes.com",
        "businessinsider.com",
        "cnbc.com",
        "bobvila.com",
        "thisoldhouse.com",
        "thespruce.com",
        "familyhandyman.com",
        "bhg.com",
        "hgtv.com",
        "goodhousekeeping.com",
        "idealhome.co.uk",
        "homebuilding.co.uk",
        "realhomes.com",
        "housebeautiful.com",
        "architecturaldigest.com",
        "dezeen.com",
        "archdaily.com",
        "designboom.com",
        "diynot.com",
        "diydata.com",
        "moneysavingexpert.com",
        "mumsnet.com",
        "netmums.com",
        "pistonheads.com",
        "redditmedia.com",
        # Website builders, domain registrars & parking networks (bare hosts)
        "wordpress.com",
        "wordpress.org",
        "blogspot.com",
        "blogger.com",
        "wix.com",
        "wixsite.com",
        "squarespace.com",
        "weebly.com",
        "godaddy.com",
        "godaddysites.com",
        "shopify.com",
        "myshopify.com",
        "bigcommerce.com",
        "webflow.io",
        "webflow.com",
        "carrd.co",
        "strikingly.com",
        "jimdo.com",
        "jimdofree.com",
        "site123.me",
        "123-reg.co.uk",
        "ionos.co.uk",
        "ionos.com",
        "namecheap.com",
        "sedo.com",
        "sedoparking.com",
        "hugedomains.com",
        "dan.com",
        "afternic.com",
        "bodis.com",
        "parkingcrew.net",
        "above.com",
        "domainmarket.com",
        "squadhelp.com",
        "atom.com",
        "brandbucket.com",
        "business.site",
        "yolasite.com",
        "angelfire.com",
        "tripod.com",
        "geocities.ws",
        "issuu.com",
        "scribd.com",
        "slideshare.net",
        "calameo.com",
        "yumpu.com",
        "eventbrite.com",
        "eventbrite.co.uk",
        "meetup.com",
        "patreon.com",
        "gofundme.com",
        "kickstarter.com",
        # Eyewear / auto-glass mega-chains that pollute "glass" searches
        "specsavers.co.uk",
        "specsavers.com",
        "visionexpress.com",
        "boots.com",
        "sunglasshut.com",
        "ray-ban.com",
        "oakley.com",
        "warbyparker.com",
        "zennioptical.com",
        "glassesdirect.co.uk",
        "eyebuydirect.com",
        "lenscrafters.com",
        "pearle.nl",
        "fielmann.de",
        "autoglass.co.uk",
        "safelite.com",
        "carglass.fr",
        "carglass.de",
        "carglass.nl",
        "carglass.be",
        "carglass.es",
        "carglass.it",
        "belron.com",
        "nationalwindscreens.co.uk",
        "obrienglass.com.au",
        "speedyglass.ca",
        "corning.com",
    }
)

# Public-suffix to ISO-3166-1 alpha-2 country inference
SUFFIX_TO_COUNTRY: dict[str, str] = {
    "uk": "GB",
    "co.uk": "GB",
    "org.uk": "GB",
    "me.uk": "GB",
    "ltd.uk": "GB",
    "plc.uk": "GB",
    "net.uk": "GB",
    "scot": "GB",
    "wales": "GB",
    "cymru": "GB",
    "london": "GB",
    "us": "US",
    "nyc": "US",
    "boston": "US",
    "miami": "US",
    "vegas": "US",
    "ca": "CA",
    "au": "AU",
    "com.au": "AU",
    "net.au": "AU",
    "org.au": "AU",
    "sydney": "AU",
    "melbourne": "AU",
    "nz": "NZ",
    "co.nz": "NZ",
    "net.nz": "NZ",
    "org.nz": "NZ",
    "ie": "IE",
    "za": "ZA",
    "co.za": "ZA",
    "org.za": "ZA",
    "net.za": "ZA",
    "de": "DE",
    "berlin": "DE",
    "hamburg": "DE",
    "bayern": "DE",
    "koeln": "DE",
    "nrw": "DE",
    "at": "AT",
    "co.at": "AT",
    "wien": "AT",
    "ch": "CH",
    "swiss": "CH",
    "li": "LI",
    "fr": "FR",
    "paris": "FR",
    "bzh": "FR",
    "alsace": "FR",
    "be": "BE",
    "brussels": "BE",
    "vlaanderen": "BE",
    "nl": "NL",
    "amsterdam": "NL",
    "frl": "NL",
    "lu": "LU",
    "es": "ES",
    "com.es": "ES",
    "cat": "ES",
    "barcelona": "ES",
    "madrid": "ES",
    "gal": "ES",
    "eus": "ES",
    "it": "IT",
    "pt": "PT",
    "com.pt": "PT",
    "pl": "PL",
    "com.pl": "PL",
    "net.pl": "PL",
    "cz": "CZ",
    "sk": "SK",
    "hu": "HU",
    "co.hu": "HU",
    "ro": "RO",
    "com.ro": "RO",
    "bg": "BG",
    "hr": "HR",
    "com.hr": "HR",
    "si": "SI",
    "rs": "RS",
    "co.rs": "RS",
    "ba": "BA",
    "gr": "GR",
    "com.gr": "GR",
    "cy": "CY",
    "com.cy": "CY",
    "mt": "MT",
    "com.mt": "MT",
    "se": "SE",
    "no": "NO",
    "dk": "DK",
    "fi": "FI",
    "is": "IS",
    "ee": "EE",
    "lv": "LV",
    "lt": "LT",
    "ua": "UA",
    "com.ua": "UA",
    "tr": "TR",
    "com.tr": "TR",
    "il": "IL",
    "co.il": "IL",
    "ae": "AE",
    "sa": "SA",
    "com.sa": "SA",
    "qa": "QA",
    "kw": "KW",
    "bh": "BH",
    "om": "OM",
    "in": "IN",
    "co.in": "IN",
    "net.in": "IN",
    "sg": "SG",
    "com.sg": "SG",
    "my": "MY",
    "com.my": "MY",
    "ph": "PH",
    "com.ph": "PH",
    "hk": "HK",
    "com.hk": "HK",
    "tw": "TW",
    "com.tw": "TW",
    "jp": "JP",
    "co.jp": "JP",
    "kr": "KR",
    "co.kr": "KR",
    "cn": "CN",
    "com.cn": "CN",
    "th": "TH",
    "co.th": "TH",
    "vn": "VN",
    "com.vn": "VN",
    "id": "ID",
    "co.id": "ID",
    "mx": "MX",
    "com.mx": "MX",
    "br": "BR",
    "com.br": "BR",
    "ar": "AR",
    "com.ar": "AR",
    "cl": "CL",
    "co.cl": "CL",
    "pe": "PE",
    "com.pe": "PE",
    "uy": "UY",
    "com.uy": "UY",
    "cr": "CR",
    "co.cr": "CR",
    "pa": "PA",
    "com.pa": "PA",
    "ng": "NG",
    "com.ng": "NG",
    "ke": "KE",
    "co.ke": "KE",
    "gh": "GH",
    "com.gh": "GH",
    "eg": "EG",
    "com.eg": "EG",
    "ma": "MA",
}

# Non-HTML asset extensions we shouldn't treat as business websites on their own when malformed
_VALID_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
_NON_HTTP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "ftp:", "file:", "blob:", "sms:", "whatsapp:")


@dataclass(slots=True, frozen=True)
class NormalizedDomain:
    """Result of cleaning and validating a candidate business website URL."""

    domain: str           # Registered root domain (eTLD+1), e.g. "acme-windows.co.uk"
    canonical_url: str    # Clean homepage URL, e.g. "https://acme-windows.co.uk"
    sld: str              # Second-level domain label, e.g. "acme-windows"
    suffix: str           # Public suffix, e.g. "co.uk"
    inferred_country: str | None  # ISO-2 from ccTLD if unambiguous, else None
    original_path: str    # Lowercased path from the input URL (useful for classifier signals)


def unwrap_redirect_url(raw_url: str, max_hops: int = 3) -> str:
    """Unwrap Google/Bing/DuckDuckGo/Facebook/Yahoo redirect wrapper URLs."""
    current = raw_url.strip()
    for _ in range(max_hops):
        if not current:
            break
        # Handle Yahoo's embedded /RU=https%3A%2F%2F.../RK= path format
        if "r.search.yahoo.com" in current and "/RU=" in current:
            m = re.search(r"/RU=([^/]+)", current)
            if m:
                current = unquote(m.group(1))
                continue

        # Handle Google's relative `/url?q=...` links
        if current.startswith("/url?"):
            current = "https://www.google.com" + current

        try:
            parsed = urlparse(current if "://" in current else f"https://{current}")
        except ValueError:
            break

        host = (parsed.hostname or "").lower().removeprefix("www.")
        param_names = _REDIRECT_HOSTS.get(host)
        if not param_names:
            break

        qs = parse_qs(parsed.query)
        next_url = None
        for key in param_names:
            vals = qs.get(key)
            if vals and vals[0]:
                candidate = unquote(vals[0]).strip()
                # Bing sometimes base64-encodes `u=a1aHR0cHM6Ly...`
                if host == "bing.com" and key == "u" and candidate.startswith("a1"):
                    import base64

                    try:
                        padded = candidate[2:] + "=" * (-len(candidate[2:]) % 4)
                        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
                        if decoded.startswith(("http://", "https://")):
                            candidate = decoded
                    except Exception:
                        pass
                if candidate.startswith(("http://", "https://", "www.")):
                    next_url = candidate
                    break
        if not next_url or next_url == current:
            break
        current = next_url
    return current


def reverse_commoncrawl_host(rev_host: str) -> str:
    """Convert Common Crawl reversed domain notation ('uk.co.acme-windows') to 'acme-windows.co.uk'."""
    parts = [p for p in rev_host.strip().lower().split(".") if p]
    parts.reverse()
    return ".".join(parts)


def is_blocked_domain(domain: str, sld: str = "", suffix: str = "") -> bool:
    """Return True if a domain belongs to a directory, social site, big tech, gov/edu, or parking host."""
    domain = domain.lower()
    if domain in BLOCKED_DOMAINS:
        return True
    if not sld or not suffix:
        ext = _EXTRACTOR(domain)
        sld = ext.domain.lower()
        suffix = ext.suffix.lower()
    if suffix in _BLOCKED_SUFFIXES:
        return True
    if suffix.startswith(("gov.", "edu.", "mil.", "ac.", "gouv.", "gob.")):
        return True
    if sld in _BLOCKED_SECOND_LEVEL_GLOBAL:
        return True
    # Catch regional Google/Amazon/eBay/Yelp variants like google.com.br, yellowpages.co.za
    if sld in ("yellow-pages", "paginas-amarillas", "pagine-gialle", "gelbe-seiten"):
        return True
    return False


def infer_country_from_suffix(suffix: str) -> str | None:
    """Infer an ISO-3166-1 alpha-2 country code from a domain's public suffix.

    Generic TLDs (.com, .net, .org, .info, .biz, .co, .io, .ai, .eu, .shop, .store, .glass, .build)
    intentionally return None because they are used globally (NOTE: .co and .io and .ai are
    treated as generic despite technically being ccTLDs).
    """
    s = suffix.lower()
    if s in SUFFIX_TO_COUNTRY:
        return SUFFIX_TO_COUNTRY[s]
    last = s.rsplit(".", 1)[-1]
    if last in ("co", "io", "ai", "tv", "me", "cc", "ws", "fm", "am", "to", "ly", "gg", "sh", "vc", "la", "eu"):
        return None
    return SUFFIX_TO_COUNTRY.get(last)


def normalize_url(raw: str | None, *, allow_infra_subdomain: bool = True) -> NormalizedDomain | None:
    """Parse, unwrap, validate, and canonicalize any candidate URL or domain string.

    Returns None if the input is malformed, an IP address, non-HTTP scheme, or on the blocklist.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip().strip("\"'<>()[]{}.,; \t\r\n")
    if not cleaned or len(cleaned) > 2048:
        return None

    # Take first URL if someone put "https://a.com; https://b.com" in an OSM website tag
    for sep in (";", " ", "\n", "\t", "|"):
        if sep in cleaned:
            cleaned = cleaned.split(sep, 1)[0].strip().rstrip(",;")

    low = cleaned.lower()
    if low.startswith(_NON_HTTP_SCHEMES):
        return None

    # Strip wildcard prefix from CT logs (*.acmewindows.co.uk)
    if cleaned.startswith("*."):
        cleaned = cleaned[2:]
    elif cleaned.startswith("//"):
        cleaned = "https:" + cleaned

    cleaned = unwrap_redirect_url(cleaned)

    if "://" not in cleaned:
        # Reject bare emails like info@acmewindows.co.uk
        if "@" in cleaned.split("/", 1)[0]:
            return None
        cleaned = "https://" + cleaned

    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return None

    if parsed.scheme.lower() not in ("http", "https"):
        return None

    host = (parsed.hostname or "").strip().lower().strip(".")
    if not host or len(host) > 253 or "." not in host:
        return None

    # Reject raw IPv4/IPv6 literals
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass

    # Encode IDN domains safely (e.g. müller-fensterbau.de -> xn--mller-fensterbau-jzb.de)
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None

    if not _VALID_HOST_RE.match(ascii_host):
        return None

    ext = _EXTRACTOR(ascii_host)
    if not ext.domain or not ext.suffix:
        return None

    # Reject private-suffix multi-tenant platforms (blogspot.com, github.io, wixsite.com, etc.)
    if ext.is_private:
        # Exception: allow real standalone UK domains like .uk.com, .gb.com, .us.com, .de.com, .eu.com, .co.com
        if ext.suffix.lower() not in ("uk.com", "gb.com", "us.com", "de.com", "eu.com", "co.com", "au.com", "za.com"):
            return None

    sub = ext.subdomain.lower()
    if not allow_infra_subdomain and sub:
        first_label = sub.split(".", 1)[0]
        if first_label in _INFRA_SUBDOMAINS and first_label != "www":
            # Still collapse to the parent registered domain rather than throwing away a valid company!
            pass

    registered = f"{ext.domain.lower()}.{ext.suffix.lower()}"

    # Readable SLD for classifier (decode punycode back to unicode so 'müller-fensterbau' matches 'fensterbau')
    try:
        readable_sld = ext.domain.lower().encode("ascii").decode("idna")
    except UnicodeError:
        readable_sld = ext.domain.lower()

    if len(readable_sld) < 2:
        return None

    suffix = ext.suffix.lower()
    if is_blocked_domain(registered, readable_sld, suffix):
        return None

    # Check if the host was a subdomain of a blocked domain (e.g. business.google.com, en.wikipedia.org)
    if registered in BLOCKED_DOMAINS:
        return None

    inferred_country = infer_country_from_suffix(suffix)
    canonical_url = f"https://{registered}"
    path = unquote(parsed.path or "").lower()

    return NormalizedDomain(
        domain=registered,
        canonical_url=canonical_url,
        sld=readable_sld,
        suffix=suffix,
        inferred_country=inferred_country,
        original_path=path,
    )
