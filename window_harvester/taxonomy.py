"""Comprehensive global window, glazing, fenestration & glass search taxonomy.

Organized by tier (1 = highest unique yield per query, 2 = sub-vertical expansion,
3 = exhaustive long-tail) and localized for UK/Commonwealth, North America, and Europe
so every query returns maximum real window businesses with zero wasted searches.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. UK / IRELAND / AUSTRALIA / NEW ZEALAND / SOUTH AFRICA KEYWORDS
# ---------------------------------------------------------------------------

UK_COMMONWEALTH_KEYWORDS_TIER1: tuple[str, ...] = (
    "double glazing",
    "window company",
    "window installers",
    "uPVC windows",
    "aluminium windows",
    "timber windows",
    "sash windows",
    "steel windows",
    "window suppliers",
    "window manufacturers",
    "glaziers",
    "glass suppliers",
    "commercial glazing",
    "replacement windows",
    "windows and doors",
)

UK_COMMONWEALTH_KEYWORDS_TIER2: tuple[str, ...] = (
    "triple glazing",
    "secondary glazing",
    "casement windows",
    "crittall windows",
    "trade windows",
    "window fabricators",
    "bifold doors and windows",
    "architectural glazing",
    "structural glazing",
    "curtain walling",
    "glass merchants",
    "sealed unit manufacturers",
    "toughened glass suppliers",
    "skylights and roof lanterns",
    "rooflights",
    "conservatories and windows",
    "orangeries",
    "window repairs",
    "misted double glazing",
    "sash window restoration",
    "heritage windows",
    "bespoke timber windows",
    "alu clad windows",
    "shopfront glazing",
    "stained glass windows",
    "leaded light windows",
    "acoustic glazing",
    "window hardware suppliers",
)

UK_COMMONWEALTH_KEYWORDS_TIER3: tuple[str, ...] = (
    "flush casement windows",
    "box sash windows",
    "hardwood windows",
    "accoya windows",
    "oak windows",
    "slimline aluminium windows",
    "thermally broken aluminium windows",
    "tilt and turn windows",
    "bay windows",
    "sliding sash windows",
    "PVCu window fabricators",
    "supply only windows",
    "wholesale windows",
    "window extrusion manufacturers",
    "metal window manufacturers",
    "bronze windows",
    "wrought iron windows",
    "fenestration contractors",
    "facade glazing contractors",
    "frameless glazing",
    "flat glass processors",
    "laminated glass suppliers",
    "fire rated glass suppliers",
    "insulated glass units",
    "cut to size glass",
    "glass balustrades and glazing",
    "emergency glazier",
    "roof window installers",
    "walk on glass rooflights",
    "passive house windows",
    "draught proofing sash windows",
    "architectural window film",
    "solar control window film",
    "window gasket and seal suppliers",
    "bespoke joinery windows",
)

# ---------------------------------------------------------------------------
# 2. US & CANADA KEYWORDS (American spelling & market terminology)
# ---------------------------------------------------------------------------

NORTH_AMERICA_KEYWORDS_TIER1: tuple[str, ...] = (
    "window installation",
    "window replacement",
    "window company",
    "window supplier",
    "window manufacturer",
    "vinyl windows",
    "aluminum windows",
    "wood windows",
    "steel windows",
    "fiberglass windows",
    "glass company",
    "glazing contractor",
    "commercial glass and glazing",
    "windows and doors",
    "glass supplier",
)

NORTH_AMERICA_KEYWORDS_TIER2: tuple[str, ...] = (
    "replacement windows",
    "custom windows",
    "casement windows",
    "double hung windows",
    "double pane windows",
    "triple pane windows",
    "architectural windows",
    "impact windows",
    "hurricane windows",
    "storm windows",
    "egress windows",
    "skylight installation",
    "curtain wall contractor",
    "storefront glass",
    "architectural glass",
    "insulated glass manufacturer",
    "tempered glass supplier",
    "flat glass distributor",
    "glazier",
    "window repair",
    "historic window restoration",
    "wholesale windows",
    "window distributor",
    "window dealer",
    "sunroom and patio enclosures",
    "stained glass studio",
    "composite windows",
    "window hardware manufacturer",
)

NORTH_AMERICA_KEYWORDS_TIER3: tuple[str, ...] = (
    "energy efficient windows",
    "bay and bow windows",
    "sliding windows",
    "awning windows",
    "tilt and turn windows",
    "european windows",
    "clad wood windows",
    "timber windows",
    "crittall steel windows",
    "iron and steel windows",
    "bronze windows",
    "bifold windows and doors",
    "multi slide glass doors",
    "fenestration manufacturer",
    "window extrusion supplier",
    "commercial window installation",
    "structural glass contractor",
    "laminated glass manufacturer",
    "low-e glass supplier",
    "foggy window repair",
    "insulated glass unit repair",
    "sash window repair",
    "millwork windows and doors",
    "passive house windows",
    "soundproof windows",
    "security window film",
    "commercial window film",
    "skylight manufacturer",
)

# ---------------------------------------------------------------------------
# 3. EUROPEAN & GLOBAL NATIVE-LANGUAGE KEYWORDS
# ---------------------------------------------------------------------------

LOCALIZED_KEYWORDS: dict[str, dict[int, tuple[str, ...]]] = {
    "DE": {
        1: ("Fensterbau", "Fenster und Türen", "Glaserei", "Fensterhersteller", "Holzfenster", "Alufenster", "Kunststofffenster", "Fenstermontage"),
        2: ("Stahlfenster", "Glashandel", "Fassadenbau Glas", "Dachfenster", "Wintergarten", "Isolierglas", "Flachglas", "Fensterreparatur", "Denkmalschutzfenster"),
    },
    "AT": {
        1: ("Fensterbau", "Fenster und Türen", "Glaserei", "Fensterhersteller", "Holz-Alu-Fenster", "Kunststofffenster"),
        2: ("Glashandel", "Wintergarten", "Dachfenster", "Isolierglas", "Fassadenverglasung"),
    },
    "CH": {
        1: ("Fensterbau", "Glaserei", "Fensterhersteller", "Holz-Metall-Fenster", "Fenêtres", "Vitrerie"),
        2: ("Kunststofffenster", "Fassadenbau Glas", "Isolierglas", "Menuiserie aluminium"),
    },
    "FR": {
        1: ("fenêtres", "menuiserie aluminium", "menuiserie PVC", "fenêtres bois", "vitrerie", "miroiterie", "fabricant de fenêtres", "double vitrage"),
        2: ("installateur fenêtres", "fenêtres acier", "verrière atelier", "mur rideau", "véranda", "fenêtre de toit", "vitrier", "vitrage isolant"),
    },
    "BE": {
        1: ("ramen en deuren", "châssis et portes", "aluminium ramen", "PVC ramen", "glaszetter", "vitrerie", "dubbel glas"),
        2: ("houten ramen", "stalen ramen", "menuiserie aluminium", "miroiterie", "veranda", "glashandel"),
    },
    "NL": {
        1: ("kozijnen", "kunststof kozijnen", "aluminium kozijnen", "houten kozijnen", "glaszetter", "glashandel", "dubbel glas", "stalen ramen"),
        2: ("ramen en deuren", "kozijnen fabriek", "isolatieglas", "HR++ glas", "dakraam", "lichtstraat", "serre aanbouw", "glas in lood"),
    },
    "ES": {
        1: ("ventanas", "ventanas PVC", "ventanas aluminio", "carpintería de aluminio", "cristalería", "fábrica de ventanas", "doble acristalamiento"),
        2: ("ventanas de madera", "cerramientos de cristal", "muro cortina", "vidrio templado", "claraboyas", "instalación de ventanas"),
    },
    "MX": {
        1: ("ventanas de aluminio", "ventanas PVC", "vidriería", "cancelería de aluminio", "fábrica de ventanas", "cristales y vidrios"),
        2: ("vidrio templado", "fachadas de cristal", "domos y tragaluces", "ventanas doble vidrio"),
    },
    "IT": {
        1: ("serramenti", "infissi", "serramenti in PVC", "serramenti in alluminio", "serramenti in legno", "vetreria", "produzione serramenti", "finestre"),
        2: ("infissi in acciaio", "doppi vetri", "facciate continue", "vetro temperato", "lucernari", "verande in vetro"),
    },
    "PT": {
        1: ("caixilharia de alumínio", "janelas PVC", "janelas de alumínio", "janelas de madeira", "vidraçaria", "fábrica de janelas", "vidros duplos"),
        2: ("caixilharia", "fachadas de vidro", "vidro temperado", "claraboias"),
    },
    "BR": {
        1: ("esquadrias de alumínio", "esquadrias de PVC", "vidraçaria", "fábrica de janelas", "janelas de madeira", "vidro temperado"),
        2: ("fachada pele de vidro", "janelas acústicas", "distribuidora de vidros", "esquadrias metálicas"),
    },
    "PL": {
        1: ("okna", "okna PCV", "okna aluminiowe", "okna drewniane", "producent okien", "stolarka okienna", "szklarz", "montaż okien"),
        2: ("hurtownia szkła", "szyby zespolone", "fasady aluminiowo szklane", "okna dachowe", "ogrody zimowe", "serwis okien"),
    },
    "CZ": {
        1: ("plastová okna", "hliníková okna", "dřevěná okna", "výroba oken", "sklenářství", "okna a dveře"),
        2: ("izolační skla", "střešní okna", "zimní zahrady", "servis oken"),
    },
    "SE": {
        1: ("fönster", "fönsterbyte", "glasmästeri", "fönstertillverkare", "träfönster", "aluminiumfönster", "PVC fönster"),
        2: ("fönsterrenovering", "takfönster", "uterum", "isolerglas"),
    },
    "NO": {
        1: ("vinduer", "glassmester", "vindusfabrikk", "aluminiumsvinduer", "trevinduer", "vinduer og dører"),
        2: ("isolerglass", "takvindu", "vinterhage", "fasadeglass"),
    },
    "DK": {
        1: ("vinduer", "glarmester", "vinduer og døre", "træ alu vinduer", "vinduesproducent", "termoruder"),
        2: ("plastvinduer", "ovenlysvinduer", "udestue", "energiruder"),
    },
    "FI": {
        1: ("ikkunat", "ikkunaremontti", "lasiliike", "ikkunatehdas", "puu-alumiini-ikkunat"),
        2: ("lasitusliike", "eristyslasi", "kattoikkuna"),
    },
    "RO": {
        1: ("ferestre termopan", "tâmplărie PVC", "tâmplărie aluminiu", "geamuri termopan", "producător ferestre", "sticlărie"),
        2: ("ferestre lemn stratificat", "pereți cortină", "geam securizat"),
    },
    "HU": {
        1: ("műanyag ablak", "nyílászáró", "fa ablak", "alumínium ablak", "üveges", "ablakgyártás"),
        2: ("hőszigetelt üveg", "tetőablak", "télikert", "ablakcsere"),
    },
    "GR": {
        1: ("κουφώματα αλουμινίου", "κουφώματα PVC", "υαλοπίνακες", "τζάμια κρύσταλλα", "ξύλινα κουφώματα"),
        2: ("ενεργειακά κουφώματα", "διπλά τζάμια"),
    },
}

# Optional extra keyword packs when user enables toggleable sub-verticals
TREATMENT_KEYWORDS: tuple[str, ...] = (
    "window shutters",
    "plantation shutters",
    "window blinds manufacturer",
    "window blinds and shutters",
)
CLEANING_KEYWORDS: tuple[str, ...] = (
    "window cleaning company",
    "commercial window cleaning",
)
AUTO_GLASS_KEYWORDS: tuple[str, ...] = (
    "auto glass repair",
    "windscreen replacement",
)

# Search-engine B2B trade/industry discovery queries (run nationwide per country, no city needed!)
TRADE_AND_MANUFACTURER_QUERIES: dict[str, tuple[str, ...]] = {
    "GB": (
        '"FENSA registered" double glazing windows',
        '"CERTASS" registered windows installer',
        '"Glass and Glazing Federation" member windows',
        '"Secured by Design" window manufacturer UK',
        '"REHAU" authorised window fabricator UK',
        '"VEKA" window fabricator UK',
        '"Liniar" window fabricator supplier UK',
        '"Deceuninck" window fabricator UK',
        '"Kommerling" window manufacturer UK',
        '"AluK" aluminium window fabricator UK',
        '"Smart Architectural Aluminium" fabricator UK',
        '"Reynaers" aluminium windows installer UK',
        '"Schuco" aluminium windows partner UK',
        '"Cortizo" sliding doors windows installer UK',
        '"Origin" aluminium windows accredited installer UK',
        '"Residence 9" windows installer UK',
        '"Accoya" timber windows manufacturer UK',
        '"Crittall" steel windows specialist UK',
        '"Pilkington" glass stockist processor UK',
        '"BS EN 1279" sealed unit manufacturer UK',
        '"BS EN 12150" toughened glass manufacturer UK',
        "trade uPVC windows fabricator UK",
        "trade aluminium windows manufacturer UK",
        "bespoke box sash windows joinery UK",
        "commercial curtain walling contractor UK",
        "architectural glazing contractor UK",
        "flat glass processor wholesale UK",
        "window hardware ironmongery supplier UK",
    ),
    "US": (
        '"NFRC" certified window manufacturer',
        '"FGIA" OR "AAMA" window manufacturer',
        '"WDMA" window and door manufacturer',
        '"Energy Star" replacement window company',
        '"Andersen" certified window contractor',
        '"Pella" certified window contractor',
        '"Marvin" authorized window dealer',
        '"Milgard" certified window dealer',
        '"Kawneer" glazing contractor storefront',
        '"YKK AP" commercial glazing contractor',
        '"Oldcastle BuildingEnvelope" glazing contractor',
        '"Cardinal Glass" OR "Guardian Glass" fabricator',
        '"IGMA" OR "IGCC" insulated glass manufacturer',
        '"Miami-Dade approved" impact windows',
        "vinyl window extrusion manufacturer USA",
        "commercial curtain wall glazing contractor",
        "architectural steel window manufacturer USA",
        "custom wood window millwork manufacturer",
        "wholesale flat glass distributor USA",
        "window hardware manufacturer supplier USA",
    ),
    "CA": (
        '"SAWDAC" OR "Fenestration Canada" window manufacturer',
        '"Energy Star" window manufacturer Canada',
        "vinyl window manufacturer Ontario Quebec BC Alberta",
        "triple pane window manufacturer Canada",
        "commercial glazing curtain wall contractor Canada",
        "architectural aluminum window manufacturer Canada",
    ),
    "AU": (
        '"AGWA" Australian Glass and Window Association member',
        '"WERS" rated aluminium windows Australia',
        '"AWS" Architectural Window Systems fabricator Australia',
        '"Capral" aluminium windows fabricator Australia',
        "double glazed windows manufacturer Australia",
        "bushfire BAL rated windows manufacturer Australia",
        "toughened glass processor wholesale Australia",
        "commercial glazing facade contractor Australia",
    ),
    "IE": (
        '"NSAI" certified windows manufacturer Ireland',
        "uPVC windows manufacturer supplier Ireland",
        "triple glazing windows installer Ireland",
        "aluminium windows passive house Ireland",
        "architectural glazing contractor Ireland",
    ),
    "NZ": (
        '"WANZ" Window Association New Zealand',
        '"APL" OR "Altherm" OR "First Windows" aluminium joinery NZ',
        "double glazing retrofit New Zealand",
        "thermally broken aluminium windows NZ",
        "glass merchant glazier New Zealand",
    ),
}

# ---------------------------------------------------------------------------
# 4. CERTIFICATE TRANSPARENCY (crt.sh) DOMAIN DISCOVERY PATTERNS
# ---------------------------------------------------------------------------
# Carefully scoped so each query completes fast without timing out crt.sh,
# while collectively sweeping every fenestration niche & country TLD.

CRTSH_PATTERNS: tuple[str, ...] = (
    # Double / triple / secondary glazing
    "%doubleglazing%",
    "%double-glazing%",
    "%tripleglazing%",
    "%triple-glazing%",
    "%secondaryglazing%",
    "%secondary-glazing%",
    "%acousticglazing%",
    "%thermalglazing%",
    "%mistedwindow%",
    "%mistedunit%",
    # Glazing & glaziers by TLD
    "%glazing%.co.uk",
    "%glazing%.uk",
    "%glazing%.com",
    "%glazing%.com.au",
    "%glazing%.co.nz",
    "%glazing%.ie",
    "%glazing%.ca",
    "%glazing%.net",
    "%glazier%",
    "%glaziery%",
    # uPVC & Vinyl
    "%upvcwindow%",
    "%upvc-window%",
    "%upvc%.co.uk",
    "%upvc%.ie",
    "%pvcu%",
    "%vinylwindow%",
    "%vinyl-window%",
    # Timber, Wood, Sash, Casement
    "%sashwindow%",
    "%sash-window%",
    "%timberwindow%",
    "%timber-window%",
    "%woodwindow%",
    "%wood-window%",
    "%woodenwindow%",
    "%wooden-window%",
    "%casementwindow%",
    "%casement-window%",
    "%heritagewindow%",
    "%heritage-window%",
    "%aluclad%",
    "%draughtproof%",
    # Aluminium, Bi-fold, Sliding
    "%aluminiumwindow%",
    "%aluminium-window%",
    "%aluminumwindow%",
    "%aluminum-window%",
    "%aliwindow%",
    "%aluwindow%",
    "%bifolddoor%",
    "%bifold-door%",
    "%bifoldwindow%",
    "%slimlinewindow%",
    "%tiltandturn%",
    # Steel & Crittall
    "%steelwindow%",
    "%steel-window%",
    "%crittall%",
    "%metalwindow%",
    "%metal-window%",
    "%bronzewindow%",
    "%ironwindow%",
    # Manufacturers, Suppliers, Trade, Fabricators
    "%windowsuppli%",
    "%window-suppli%",
    "%windowmanufactur%",
    "%window-manufactur%",
    "%windowfabricat%",
    "%window-fabricat%",
    "%tradewindow%",
    "%trade-window%",
    "%windowtrade%",
    "%windowwholesal%",
    "%windowfactory%",
    "%windowhardware%",
    "%sealedunit%",
    "%sealed-unit%",
    "%insulatedglass%",
    "%insulated-glass%",
    # Installers, Replacement, Repair, Windows & Doors
    "%windowreplacement%",
    "%window-replacement%",
    "%replacementwindow%",
    "%replacement-window%",
    "%windowinstall%",
    "%window-install%",
    "%windowfitter%",
    "%window-fitter%",
    "%windowrepair%",
    "%window-repair%",
    "%windowrestor%",
    "%windowdoctor%",
    "%windowsanddoors%",
    "%windows-and-doors%",
    "%doorsandwindows%",
    "%doors-and-windows%",
    "%windowanddoor%",
    "%window-and-door%",
    "%windowcompany%",
    "%window-company%",
    "%windowsdirect%",
    "%windows-direct%",
    "%impactwindow%",
    "%impact-window%",
    "%hurricanewindow%",
    "%hurricane-window%",
    "%stormwindow%",
    "%storm-window%",
    "%egresswindow%",
    "%fiberglasswindow%",
    "%compositewindow%",
    "%customwindow%",
    "%custom-window%",
    "%bespokewindow%",
    "%bespoke-window%",
    # TLD-scoped broader window business certs
    "%windows.co.uk",
    "%windows.uk",
    "%windows.ie",
    "%windows.com.au",
    "%windows.co.nz",
    "%windows.ca",
    "%windows.co.za",
    "%windows.us",
    # Commercial, Curtain Wall, Fenestration, Glass
    "%fenestration%",
    "%curtainwall%",
    "%curtain-wall%",
    "%architecturalglaz%",
    "%architecturalglass%",
    "%architectural-glass%",
    "%structuralglaz%",
    "%structuralglass%",
    "%commercialglaz%",
    "%commercialglass%",
    "%commercial-glass%",
    "%shopfrontglaz%",
    "%storefrontglass%",
    "%glassandglazing%",
    "%glass-and-glazing%",
    "%glassmerchant%",
    "%glass-merchant%",
    "%glasssupplier%",
    "%glass-supplier%",
    "%toughenedglass%",
    "%temperedglass%",
    "%laminatedglass%",
    "%flatglass%",
    "%windowglass%",
    "%stainedglass%",
    "%stained-glass%",
    "%leadedlight%",
    "%.glass",
    # Skylights, Roof Lanterns, Conservatories, Sunrooms
    "%skylight%",
    "%rooflantern%",
    "%roof-lantern%",
    "%rooflight%",
    "%roof-light%",
    "%roofwindow%",
    "%roof-window%",
    "%conservatories.co.uk",
    "%orangeries.co.uk",
    "%sunroom%",
    "%windowfilm%",
    "%window-film%",
    # Major European fenestration stems
    "%fensterbau%",
    "%glaserei%",
    "%glashandel%",
    "%holzfenster%",
    "%alufenster%",
    "%dachfenster%",
    "%isolierglas%",
    "%vitrerie%",
    "%miroiterie%",
    "%menuiserie-alu%",
    "%menuiserie-pvc%",
    "%double-vitrage%",
    "%kozijnen%",
    "%glaszetter%",
    "%dubbelglas%",
    "%serramenti%",
    "%infissi%",
    "%vetreria%",
    "%cristaleria%",
    "%ventanaspvc%",
    "%ventanas-pvc%",
    "%ventanasaluminio%",
    "%stolarkaokienna%",
    "%oknapvc%",
    "%okna-pvc%",
    "%szklarz%",
    "%caixilharia%",
    "%esquadrias%",
    "%vidracaria%",
    "%glarmester%",
    "%vinduer.dk",
    "%vinduer.no",
    "%glasmastare%",
)

# ---------------------------------------------------------------------------
# 5. COMMON CRAWL CDX SERVICE-PAGE PATTERNS
# ---------------------------------------------------------------------------
# Discovers window companies whose root domain does NOT contain "window" or "glass"
# (e.g. smithjoinery.co.uk/sash-windows, apexhomeimprovements.com/window-replacement).

CDX_PATH_SLUGS_GLOBAL: tuple[str, ...] = (
    "double-glazing*",
    "triple-glazing*",
    "secondary-glazing*",
    "upvc-windows*",
    "sash-windows*",
    "timber-windows*",
    "wooden-windows*",
    "wood-windows*",
    "aluminium-windows*",
    "aluminum-windows*",
    "steel-windows*",
    "crittall-windows*",
    "vinyl-windows*",
    "fiberglass-windows*",
    "casement-windows*",
    "bifold-doors*",
    "replacement-windows*",
    "window-replacement*",
    "window-installation*",
    "window-repair*",
    "impact-windows*",
    "hurricane-windows*",
    "commercial-glazing*",
    "architectural-glazing*",
    "structural-glazing*",
    "curtain-walling*",
    "curtain-wall*",
    "skylights*",
    "roof-lanterns*",
    "rooflights*",
    "sealed-units*",
    "toughened-glass*",
    "glazing-services*",
    "glaziers*",
    "glass-suppliers*",
    "glass-merchants*",
    "window-suppliers*",
    "window-manufacturers*",
    "window-fabricators*",
    "trade-windows*",
    "conservatories*",
    "orangeries*",
    "windows-and-doors*",
)

CDX_TARGET_TLDS: dict[str, str] = {
    "GB": "co.uk",
    "UK": "uk",
    "US": "com",
    "CA": "ca",
    "AU": "com.au",
    "NZ": "co.nz",
    "IE": "ie",
    "ZA": "co.za",
    "DE": "de",
    "AT": "at",
    "CH": "ch",
    "FR": "fr",
    "BE": "be",
    "NL": "nl",
    "ES": "es",
    "IT": "it",
    "PT": "pt",
    "PL": "pl",
    "SE": "se",
    "NO": "no",
    "DK": "dk",
    "CZ": "cz",
    "RO": "ro",
}

CDX_LOCALIZED_SLUGS: dict[str, tuple[str, ...]] = {
    "DE": ("fensterbau*", "holzfenster*", "kunststofffenster*", "aluminiumfenster*", "glaserei*", "isolierglas*", "dachfenster*"),
    "AT": ("fensterbau*", "holz-alu-fenster*", "glaserei*", "kunststofffenster*"),
    "CH": ("fensterbau*", "glaserei*", "fenetres*", "vitrerie*"),
    "FR": ("menuiserie-aluminium*", "fenetres-pvc*", "fenetres-aluminium*", "fenetres-bois*", "vitrerie*", "miroiterie*", "double-vitrage*"),
    "BE": ("ramen-en-deuren*", "aluminium-ramen*", "pvc-ramen*", "chassis-pvc*", "vitrerie*"),
    "NL": ("kunststof-kozijnen*", "aluminium-kozijnen*", "houten-kozijnen*", "dubbel-glas*", "glaszetter*", "stalen-ramen*"),
    "ES": ("ventanas-pvc*", "ventanas-aluminio*", "carpinteria-aluminio*", "cristaleria*", "doble-acristalamiento*"),
    "IT": ("serramenti-pvc*", "serramenti-alluminio*", "serramenti-legno*", "infissi-pvc*", "vetreria*", "facciate-continue*"),
    "PT": ("caixilharia-aluminio*", "janelas-pvc*", "vidros-duplos*", "vidracaria*"),
    "PL": ("okna-pcv*", "okna-pvc*", "okna-aluminiowe*", "okna-drewniane*", "stolarka-okienna*", "szyby-zespolone*"),
    "SE": ("fonsterbyte*", "glasmasteri*", "trafonster*"),
    "NO": ("vinduer*", "glassmester*", "isolerglass*"),
    "DK": ("vinduer-og-doere*", "glarmester*", "termoruder*"),
    "CZ": ("plastova-okna*", "hlinikova-okna*", "drevena-okna*", "sklenarstvi*"),
    "RO": ("tamplarie-pvc*", "ferestre-termopan*", "pereti-cortina*"),
}

# ---------------------------------------------------------------------------
# 6. YELLOWPAGES CATEGORIES & UK COMPANIES HOUSE SIC CODES
# ---------------------------------------------------------------------------

YELLOWPAGES_US_TERMS: tuple[str, ...] = (
    "windows",
    "windows repair replacement and installation",
    "vinyl windows",
    "wood windows",
    "metal windows",
    "storm windows and doors",
    "glass plate window etc",
    "glaziers",
    "window manufacturers",
    "skylights",
    "glass block",
    "stained and leaded glass",
    "sunrooms and solariums",
)

# Official UK Companies House SIC 2007 codes covering every window & glass business in Britain
UK_COMPANIES_HOUSE_SIC_CODES: dict[str, tuple[str, str]] = {
    "43342": ("Glazing (double glazing, window glazing & glaziers)", "double_triple_glazing"),
    "25120": ("Manufacture of doors and windows of metal (aluminium & steel)", "aluminium"),
    "22230": ("Manufacture of builders' ware of plastic (uPVC windows & frames)", "upvc_vinyl"),
    "16230": ("Manufacture of other builders' carpentry and joinery (timber & sash windows)", "timber_wood"),
    "23110": ("Manufacture of flat glass", "glass_glaziers"),
    "23120": ("Shaping and processing of flat glass (toughened, laminated & sealed units)", "glass_glaziers"),
    "43320": ("Joinery installation (window & door fitting — filtered by window/glazing name)", "installers_replacement"),
}


def get_keywords_for_country(
    country: str,
    *,
    max_tier: int = 2,
    include_treatments: bool = False,
    include_window_cleaning: bool = False,
    include_auto_glass: bool = False,
    custom_keywords: list[str] | None = None,
) -> list[str]:
    """Return deduplicated, priority-ordered search keywords tailored to `country`."""
    if custom_keywords:
        return list(dict.fromkeys(k.strip() for k in custom_keywords if k.strip()))

    cc = country.upper()
    out: list[str] = []

    if cc in ("US", "CA"):
        out.extend(NORTH_AMERICA_KEYWORDS_TIER1)
        if max_tier >= 2:
            out.extend(NORTH_AMERICA_KEYWORDS_TIER2)
        if max_tier >= 3:
            out.extend(NORTH_AMERICA_KEYWORDS_TIER3)
    elif cc in LOCALIZED_KEYWORDS:
        tiers = LOCALIZED_KEYWORDS[cc]
        out.extend(tiers.get(1, ()))
        if max_tier >= 2:
            out.extend(tiers.get(2, ()))
        if max_tier >= 3:
            # Supplement with top international English B2B manufacturer terms
            out.extend(("window manufacturer", "architectural glazing", "glass manufacturer", "aluminium windows"))
    else:
        # GB, IE, AU, NZ, ZA, SG, AE, IN, and default international English
        out.extend(UK_COMMONWEALTH_KEYWORDS_TIER1)
        if max_tier >= 2:
            out.extend(UK_COMMONWEALTH_KEYWORDS_TIER2)
        if max_tier >= 3:
            out.extend(UK_COMMONWEALTH_KEYWORDS_TIER3)

    if include_treatments:
        out.extend(TREATMENT_KEYWORDS)
    if include_window_cleaning:
        out.extend(CLEANING_KEYWORDS)
    if include_auto_glass:
        out.extend(AUTO_GLASS_KEYWORDS)

    return list(dict.fromkeys(out))


def build_cdx_patterns(countries: list[str] | None = None) -> list[tuple[str, str]]:
    """Generate `(url_wildcard_pattern, inferred_country_or_empty)` pairs for Common Crawl CDX."""
    selected = [c.upper() for c in countries] if countries else list(CDX_TARGET_TLDS.keys())
    patterns: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(pat: str, cc: str) -> None:
        if pat not in seen:
            seen.add(pat)
            patterns.append((pat, cc))

    english_ccs = {"GB", "UK", "US", "CA", "AU", "NZ", "IE", "ZA"}
    for cc in selected:
        tld = CDX_TARGET_TLDS.get(cc)
        if not tld:
            continue
        inferred = "" if tld == "com" else ("GB" if cc == "UK" else cc)
        if cc in english_ccs:
            for slug in CDX_PATH_SLUGS_GLOBAL:
                _add(f"*.{tld}/{slug}", inferred)
            if cc == "GB":
                # Also sweep newer *.uk root domains
                for slug in CDX_PATH_SLUGS_GLOBAL[:18]:
                    _add(f"*.uk/{slug}", "GB")
        elif cc in CDX_LOCALIZED_SLUGS:
            for slug in CDX_LOCALIZED_SLUGS[cc]:
                _add(f"*.{tld}/{slug}", inferred)

    return patterns
