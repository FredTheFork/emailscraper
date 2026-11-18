"""High-precision Window, Glazing & Glass Business Classifier and Noise Filter.

Engineered specifically to separate real architectural/building window, glazing, frame,
skylight, conservatory, and flat-glass businesses from massive internet noise:
  - Microsoft Windows OS, software, drivers, keys, hosting, forums, tech blogs
  - Eyewear, opticians, sunglasses, spectacles, contact lenses ("glasses")
  - Drinkware, wine/pint glasses, glass bottles/jars, lab glass, smoking glass, jewelry
  - Automotive windshields/carglass, phone screen repair, fiberglass boats/pools
  - Music/dance/nature conservatories, parked/for-sale domains
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from window_harvester.domains import NormalizedDomain, normalize_url
from window_harvester.models import ClassificationResult, FilterOptions

# ---------------------------------------------------------------------------
# 1. SUB-CATEGORY KEYWORD PATTERNS (works on both concatenated SLDs & text)
# ---------------------------------------------------------------------------

# High-specificity compound stems safe for bare-domain (100M+ host) scanning.
# Each tuple is (category_slug, confidence, compiled_regex).
_STRONG_DOMAIN_PATTERNS: tuple[tuple[str, float, re.Pattern[str]], ...] = (
    (
        "double_triple_glazing",
        0.95,
        re.compile(
            r"(?:double|triple|secondary|acoustic|thermal|solar|slimline|heritage|vacuum)[-_]?glaz"
            r"|doppelverglas|dubbelglas|double[-_]?vitrage|doppi[-_]?vetri|doble[-_]?acristalamiento"
            r"|misted[-_]?(?:window|unit|glass|double)",
            re.I,
        ),
    ),
    (
        "upvc_vinyl",
        0.94,
        re.compile(
            r"(?:upvc|pvcu)(?:[-_]?(?:window|door|glaz|frame|conservator|suppli|trade|repair|spray|fascia|home|direct|pro|uk|ltd))?"
            r"|vinyl[-_]?window|pvc[-_]?(?:window|fenster|fenetre|kozijn|ventana|serrament|infiss|okna|janel)"
            r"|(?:fenster|fenetre|kozijn|ventana|serrament|infiss|okna)[-_]?pvc"
            r"|menuiserie[-_]?pvc",
            re.I,
        ),
    ),
    (
        "timber_wood",
        0.94,
        re.compile(
            r"(?:timber|wood|wooden|hardwood|softwood|oak|accoya|aluclad|alu[-_]?clad)[-_]?window"
            r"|(?:sash|box[-_]?sash|sliding[-_]?sash|casement|flush[-_]?casement|georgian|victorian|heritage)[-_]?window"
            r"|holz[-_]?fenster|holzalu[-_]?fenster|fenetre[-_]?bois|houten[-_]?kozijn"
            r"|ventana[s]?[-_]?madera|serramenti[-_]?legno|okna[-_]?drewnian"
            r"|draught[-_]?proof|sash[-_]?(?:restor|repair|renovat|glaz|joinery|cord)",
            re.I,
        ),
    ),
    (
        "aluminium",
        0.95,
        re.compile(
            r"(?:aluminium|aluminum|ali|alu)[-_]?(?:window|glaz|bifold|bi[-_]?fold|fenestration|curtain|shopfront|frame|system)"
            r"|(?:bifold|bi[-_]?fold|sliding|tilt[-_]?(?:and[-_]?)?turn|slimline)[-_]?(?:window|door|glaz)"
            r"|alu[-_]?fenster|fenetre[-_]?alu|menuiserie[-_]?alu|aluminium[-_]?kozijn"
            r"|carpinteria[-_]?(?:aluminio|metalica)|ventana[s]?[-_]?aluminio"
            r"|serramenti[-_]?alluminio|infissi[-_]?alluminio|okna[-_]?aluminiow|esquadria[s]?[-_]?aluminio",
            re.I,
        ),
    ),
    (
        "steel_crittall",
        0.95,
        re.compile(
            r"(?:steel|crittall|crittal|wrought[-_]?iron|bronze|metal|industrial|art[-_]?deco)[-_]?(?:window|glaz|casement|fenestration)"
            r"|stahl[-_]?fenster|fenetre[-_]?acier|stalen[-_]?(?:raam|ramen|kozijn|deur)",
            re.I,
        ),
    ),
    (
        "commercial_curtain_wall",
        0.93,
        re.compile(
            r"curtain[-_]?wall|fenestration|(?:architectural|structural|commercial|contract|bespoke|frameless)[-_]?(?:glaz|glass|window)"
            r"|(?:shopfront|shop[-_]?front|storefront|store[-_]?front)[-_]?(?:glaz|glass|window|aluminium|aluminum)"
            r"|glasfassade|facade[-_]?verre|mur[-_]?rideau|facciata[-_]?continua|muro[-_]?cortina",
            re.I,
        ),
    ),
    (
        "manufacturers_suppliers",
        0.93,
        re.compile(
            r"window[-_]?(?:suppli|manufactur|fabricat|extrud|wholesal|trade|factory|works|system|profile|hardware|hinge|handle|seal|gasket|part)"
            r"|trade[-_]?(?:window|glaz|frame|upvc|bifold)"
            r"|(?:glass|glazing)[-_]?(?:suppli|manufactur|merchant|processor|wholesal|trade|works|factory)"
            r"|(?:sealed|insulated|insulating|igu|dgu)[-_]?(?:unit|glass)"
            r"|fensterbau|fensterfabrik|fensterwerk|glashandel|glasgro[s]?handel|stolarka[-_]?okienn|fabryka[-_]?okien",
            re.I,
        ),
    ),
    (
        "installers_replacement",
        0.93,
        re.compile(
            r"(?:replacement|impact|hurricane|storm|egress|bay|bow|awning|hopper|picture|fiberglass|composite|energy|custom|home|house|residential)[-_]?window"
            r"|window[-_]?(?:replacement|install|fitter|fitting|repair|restor|renovat|doctor|medic|surgeon|guru|wizard|specialist|expert|service|solution|company|corp|group|depot|world|nation|direct|plus|pro|pros|mart|warehouse|outlet|centre|center|shop|store|studio|craft|master|king|guys|man|men|source|express|choice|connection|works)"
            r"|window[s]?[-_]?(?:and[-_]?|n[-_]?)?door[s]?|door[s]?[-_]?(?:and[-_]?|n[-_]?)?window[s]?"
            r"|window[s]?[-_]?(?:and[-_]?)?(?:conservator|siding|roofing|glazing|glass|joinery|home|exterior|gutter|fascia|soffit)"
            r"|fenster[-_]?(?:montage|service|technik|profi|handel|welt|direkt|konzept|system|design|werkstatt|reparatur)"
            r"|pose[-_]?fenetre|serramenti|infissi|kozijnen|caixilharia|esquadrias",
            re.I,
        ),
    ),
    (
        "glass_glaziers",
        0.92,
        re.compile(
            r"glazier|glaziery|glazing"
            r"|(?:toughened|tempered|laminated|annealed|float|flat|plate|low[-_]?e|pilkington|balustrade|splashback|shower|mirror|partition|fire[-_]?rated|obscure|patterned|satin|frosted|wired|safety|security)[-_]?glass"
            r"|glass[-_]?(?:and[-_]?)?(?:glaz|window|mirror|door|aluminium|aluminum|balustrade|splashback|cut|repair|replace|install|service|company|work|merchant|centre|center|direct|express|doctor|pro|specialist|solution|studio|group)"
            r"|window[-_]?glass"
            r"|glaserei|glasermeister|glaszetter|vitrerie|vitrier|miroiterie|vetreria|vetraio|cristaleria|cristalero|vidracaria|vidraria|szklarz|zaklad[-_]?szklarski|glarmester|glasmaestare|glasmastare",
            re.I,
        ),
    ),
    (
        "skylights_conservatories",
        0.90,
        re.compile(
            r"skylight|sky[-_]?light|roof[-_]?(?:window|lantern|light|glaz)|velux|walk[-_]?on[-_]?glass"
            r"|oranger(?:y|ies)|sunroom|patio[-_]?enclosure|dachfenster|lichtkuppel|fenetre[-_]?de[-_]?toit|dakraam|lichtstraat"
            r"|conservator(?:y|ies)[-_]?(?:roof|window|door|glaz|warm|outlet|village|world|direct|land|blinds|install|build|design|company|uk)",
            re.I,
        ),
    ),
    (
        "stained_decorative_glass",
        0.88,
        re.compile(
            r"(?:stained|leaded|bevelled|beveled|etched|fused|art[-_]?deco|church|architectural[-_]?art)[-_]?glass"
            r"|leaded[-_]?light|bleiverglasung|vitrail|vitraux|glas[-_]?in[-_]?lood",
            re.I,
        ),
    ),
)

# Foreign-language standalone window words safe for domain matching when on regional TLDs or business forms
_MULTILINGUAL_WINDOW_DOMAIN_RE = re.compile(
    r"(?:^|[-_])(?:fenster|fenetres|fenetre|ventanas|finestre|vinduer|fonster|ikkunat|janelas|ferestre|okna|okenni)(?:$|[-_])",
    re.I,
)

# Standalone English "window" / "windows" / "glass" / "conservatory" detector in domains
_BARE_WINDOW_RE = re.compile(r"window", re.I)
_BARE_GLASS_RE = re.compile(r"glass(?!es)", re.I)  # Excludes "glasses" (eyewear/drinkware!)
_PLURAL_GLASSES_RE = re.compile(r"glasses", re.I)
_BARE_CONSERVATORY_RE = re.compile(r"conservator(?:y|ies)", re.I)
_WINDOW_CLEANING_RE = re.compile(
    r"(?:window|glass|gutter|exterior|conservatory|solar)[-_]?(?:clean|wash|shine|gleam|sparkle|squeegee|valet|hygiene)"
    r"|(?:clean|wash|sparkle|gleam|squeegee)[-_]?(?:my[-_]?)?window"
    r"|fensterreinigung|glasreinigung|glazenwasser|lavage[-_]?vitre|nettoyage[-_]?vitre|limpieza[-_]?cristal",
    re.I,
)
_WINDOW_TREATMENT_ONLY_RE = re.compile(
    r"(?:blind|shutter|curtain(?!wall)|drape|drapery|shade|pelmet|valance|venetian|roller[-_]?blind|plantation[-_]?shutter|roman[-_]?blind|markise|rollladen|volet|persiana|tapparell|zonwering|rolet)",
    re.I,
)
_WINDOW_TINT_RE = re.compile(
    r"(?:window|glass|solar|privacy|security|architectural|building|home|office|manifestation)[-_]?(?:film|tint)"
    r"|(?:tint|film)[-_]?window",
    re.I,
)
_AUTO_GLASS_RE = re.compile(
    r"auto[-_]?glass|car[-_]?glass|truck[-_]?glass|rv[-_]?glass|van[-_]?glass|bus[-_]?glass|fleet[-_]?glass"
    r"|windshield|windscreen|pare[-_]?brise|autoglas|parabrisas|parabrezza|szyby[-_]?samochod"
    r"|(?:auto|car|vehicle|motor|mobile|tint[-_]?world|ceramic)[-_]?(?:window[-_]?)?tint",
    re.I,
)

# ---------------------------------------------------------------------------
# 2. HARD NEGATIVE PATTERNS (Microsoft Windows OS, Eyewear, Drinkware, etc.)
# ---------------------------------------------------------------------------

# Microsoft Windows OS / Software / Computing negatives (domain SLD level)
_MS_WINDOWS_DOMAIN_NEG_RE = re.compile(
    r"windows[-_]?(?:95|98|2000|me|nt|xp|vista|7|8|10|11|12|365|ce|rt|iot|pe|se|arm|server|phone|mobile|live|update|defender|firewall|security|azure|store|insider|central|latest|report|club|forum|forums|blog|news|tips|tricks|help|support|guide|tutorial|howto|faq|wiki|doc|docs|dev|sdk|api|cli|cmd|app|apps|soft|software|program|tool|tools|util|utility|utilities|driver|drivers|key|keys|license|licence|activat|loader|kms|iso|download|installs|setup|patch|hotfix|update|upgrade|fix|fixer|error|repair[-_]?tool|recover|recovery|backup|restore|boot|pe|password|registry|reg|clean[-_]?pc|optimiz|tweak|theme|themes|skin|skins|wallpaper|icon|icons|widget|gadget|font|cursor|screensaver|audio|media|movie|maker|player|photo|mail|messenger|hello|copilot|recall|sandbox|subsystem|wsl|terminal|powershell|script|admin|sysadmin|network|domain|ad|hosting|host|vps|vds|rdp|cloud|vm|virtual|hyperv|server|sql|iis|exchange|desktop|laptop|tablet|surface|pc|computer|tech|geek|nerd|guru[-_]?pc|mag|magazine|daily|weekly|digest|podcast|review|gamer|gaming|game|games|emulator|spot|area|zone|base|hub[-_]?it|italia[-_]?blog|espanol)"
    r"|(?:^|[-_])win(?:95|98|2k|nt|xp|7|8|10|11|12|32|64|server|soft|zip|rar|amp|scp|pcap|dir|get|et|pe|re|rt|ui|forms|api|sdk|drv|key|iso|kms|vps|rdp)(?:$|[-_])"
    r"|microsoft|powershell|active[-_]?directory|dotnet|visual[-_]?studio|csharp|sysinternal|freeware|shareware|open[-_]?source|warez|crack|keygen|serial|torrent|apk|exe|dll|msi[-_]?install|antivirus|malware|spyware|ransomware|trojan|adware|rootkit|firewall|vpn|proxy|linux|ubuntu|debian|fedora|archlinux|macos|osx|macbook|apple|iphone|ipad|android|chromebook|chromeos|firefox|browser|plugin|extension|addon|codec|bitrate|cpu|gpu|motherboard|bios|uefi|ssd|nvme|hard[-_]?drive|usb|bluetooth|wifi|router|ethernet|server|hosting|webhost|cpanel|plesk|datacenter|cloud[-_]?comput|devops|kubernetes|docker|vmware|citrix|rdp|ssh|ftp|smtp|sql|database|python|golang|javascript|typescript|java|rustlang|cplusplus|github|coding|programm|developer|software|saas|erp|crm|helpdesk|it[-_]?support|pc[-_]?repair|computer[-_]?repair|laptop[-_]?repair|data[-_]?recover|cyber[-_]?sec|infosec|hacking|hacker|gamer|gaming|esport|minecraft|roblox|fortnite|steam|xbox|playstation|nintendo|casino|betting|poker|slots|jackpot|lottery|crypto|bitcoin|ethereum|blockchain|forex|trading|payday|loan[-_]?shark|porn|xxx|adult|escort|webcam|dating"
    r"|x[-_]?window|window[-_]?manager|tiling[-_]?window|sliding[-_]?window[-_]?alg|maintenance[-_]?window|transfer[-_]?window|overton[-_]?window|johari[-_]?window|context[-_]?window|launch[-_]?window|window[-_]?seat|window[-_]?shopp|shop[-_]?window[-_]?display|rear[-_]?window|secret[-_]?window|window[-_]?of[-_]?hope|window[-_]?to[-_]?the[-_]?world|windows[-_]?of[-_]?heaven",
    re.I,
)

# Non-building "glass" negatives (eyewear, drinkware, smoking, lab, jewelry, auto, marine, phone)
_NON_BUILDING_GLASS_NEG_RE = re.compile(
    r"(?:eye|sun|reading|optical|prescription|blue[-_]?light|computer|gaming|3d|vr|ar|smart|google|opera|field|spy|magnifying|looking|hour|weather|storm[-_]?glass[-_]?barom)[-_]?glass"
    r"|optician|optometr|ophthalm|eyewear|spectacle|eyecare|vision[-_]?care|contact[-_]?lens|sunglass|goggle|monocle|bifocal|varifocal"
    r"|(?:wine|champagne|cocktail|martini|whisky|whiskey|bourbon|scotch|brandy|cognac|gin|vodka|rum|tequila|shot|pint|beer|ale|craft[-_]?beer|pub|bar|drinking|water|juice|tea|coffee|espresso|latte|glencairn|rocks|highball|coupe|flute|snifter|hurricane[-_]?cocktail)[-_]?glass"
    r"|glass[-_]?(?:ware|bottle|jar|vial|ampoule|container|packaging|cup|mug|tumbler|goblet|stemware|barware|tableware|drinkware|kitchen|bowl|plate|dish|vase|ornament|figurine|sculpture|bead|pearl|pendant|jewel|earring|necklace|bracelet|ring|marble|paperweight|coaster|straw|pipe|bong|rig|bubbler|hookah|shisha|blunt|smoke|vape|dab|heady|boro|noodle|skin|hair|nail|ceiling|slipper|menagerie|castle|house[-_]?band|jaw|animals|onion|door|box[-_]?ai|node|frog|catfish|eel|squid|sponge|wing|wort)"
    r"|(?:sea|beach|milk|depression|carnival|uranium|vaseline|fenton|murano|venetian|bohemian|waterford|lalique|swarovski|tiffany[-_]?lamp|pyrex|borosilicate|quartz|lab|laboratory|scientific|medical|pharmaceutical|dental|watch|clock|iphone|ipad|samsung|pixel|phone|screen[-_]?protector|tempered[-_]?screen|gorilla|volcanic|obsidian|spun|sugar|candy|acrylic[-_]?nail)[-_]?glass"
    r"|glassblowing|glass[-_]?blow|blown[-_]?glass|lampwork|flamework|kiln[-_]?glass|hot[-_]?glass|glass[-_]?fusing[-_]?class"
    r"|fiber[-_]?glass[-_]?(?:boat|hull|marine|yacht|canoe|kayak|surf|pool|spa|hot[-_]?tub|tank|pipe|insulation|rv|camper|auto|body|bumper|fender|mold|mould|mesh|cloth|resin|mat|rod|ladder|flagpole|statue|slide)"
    r"|fibreglass[-_]?(?:boat|hull|marine|yacht|pool|roof|grp|tank|mould|resin)"
    r"|glass[-_]?fiber|glass[-_]?fibre|optic[-_]?fiber|glasfaser|fibre[-_]?optique|fibra[-_]?de[-_]?vidrio"
    r"|headshop|smokeshop|vapeshop|dispensary|cannabis|weed|420|hemp|cbd|brewery|winery|vineyard|distillery|sommelier|bartend",
    re.I,
)

# Non-building "conservatory" negatives (music, dance, theater, botanical/nature)
_NON_BUILDING_CONSERVATORY_NEG_RE = re.compile(
    r"music|dance|ballet|theat(?:re|er)|drama|acting|opera|piano|violin|guitar|symphony|orchestra|choir|vocal|jazz|arts|performing|academy|school|college|university|institute|faculty|conservatoire|botanic|plant|butterfly|park|zoo|museum|foundation|trust|society|nature|wildlife|marine|ocean",
    re.I,
)

# Strong Microsoft Windows / non-window signals in page titles, snippets & HTML
_MS_WINDOWS_TEXT_NEG_RE = re.compile(
    r"\b(?:microsoft\s+windows|windows\s+(?:11|10|8\.1|8|7|xp|vista|nt|98|95|2000|365|server|update|defender|security|firewall|insider|store|hello|copilot|terminal|subsystem|powershell|registry|explorer|media\s+player|movie\s+maker|live|phone|mobile|ce|iot|arm|pe|sandbox|key|license|activation|iso|installer|driver|drivers|bsod|blue\s+screen|task\s+manager|control\s+panel|command\s+prompt|group\s+policy|active\s+directory|bitlocker|hyper-v|directx|win32|win64|winget|wsl2?))\b"
    r"|\b(?:download\s+for\s+windows|free\s+download\s+for\s+pc|compatible\s+with\s+windows|windows\s+and\s+(?:mac|macos|linux)|macos\s+and\s+windows|operating\s+system|product\s+key|registry\s+cleaner|antivirus\s+for\s+windows|dll\s+files?|exe\s+download|windows\s+vps|rdp\s+hosting|x11\s+window\s+manager|wayland\s+compositor)\b",
    re.I,
)

_NON_WINDOW_TEXT_NEG_RE = re.compile(
    r"\b(?:prescription\s+(?:glasses|eyewear|lenses)|eye\s+exam|optometrist|contact\s+lenses|sunglasses\s+shop|blue\s+light\s+glasses|reading\s+glasses|wine\s+glasses|cocktail\s+glasses|pint\s+glasses|water\s+pipes|glass\s+bongs|dab\s+rigs|smoke\s+shop|head\s+shop|iphone\s+screen\s+repair|cell\s+phone\s+repair|fiberglass\s+(?:pool|boat|insulation)|fiber\s+optic\s+internet|conservatory\s+of\s+(?:music|dance|arts|theatre|theater))\b",
    re.I,
)

_AUTO_GLASS_TEXT_RE = re.compile(
    r"\b(?:auto\s+glass|windshield\s+(?:repair|replacement|calibration)|windscreen\s+(?:repair|replacement|chip)|adas\s+calibration|car\s+window\s+(?:repair|replacement|tinting)|vehicle\s+glass|automotive\s+glass|mobile\s+windshield)\b",
    re.I,
)

_WINDOW_CLEANING_TEXT_RE = re.compile(
    r"\b(?:window\s+clean(?:ing|er|ers)|window\s+wash(?:ing|er|ers)|gutter\s+cleaning|pressure\s+washing|pure\s+water\s+pole|reach\s+and\s+wash|commercial\s+abseil\s+cleaning|fascia\s+and\s+soffit\s+cleaning)\b",
    re.I,
)

# Strong positive signals in text/HTML proving a real architectural window/glazing/glass business
_POSITIVE_TEXT_CATEGORY_RES: tuple[tuple[str, float, re.Pattern[str]], ...] = (
    (
        "double_triple_glazing",
        0.35,
        re.compile(
            r"\b(?:double\s+glaz(?:ing|ed)|triple\s+glaz(?:ing|ed)|secondary\s+glazing|acoustic\s+glazing|thermal\s+glazing|low[- ]e\s+glass|argon[- ]filled|u[- ]value|energy[- ]rated\s+windows|misted\s+(?:double\s+glazing|units|windows)|doppelverglasung|dreifachverglasung|double\s+vitrage|dubbel\s*glas|doppi\s+vetri|doble\s+acristalamiento)\b",
            re.I,
        ),
    ),
    (
        "upvc_vinyl",
        0.35,
        re.compile(
            r"\b(?:upvc|pvc-?u|vinyl\s+windows?|rehau|veka|komerling|k[oö]mmerling|deceuninck|liniar|eurocell|synseal|profile\s+22|residence\s+[79]|halo\s+windows|spectus|duraflex|aluplast|salamander\s+windows|gealan|sch[uü]co|fen[eê]tres?\s+pvc|kunststof\s+kozijnen|ventanas?\s+(?:de\s+)?pvc|serramenti\s+in\s+pvc|okna\s+pvc|okna\s+pcv)\b",
            re.I,
        ),
    ),
    (
        "timber_wood",
        0.35,
        re.compile(
            r"\b(?:timber\s+windows?|timber\s+sash|timber\s+casement|timber\s+(?:&|and)\s+alumini?um\s+windows?|wooden\s+windows?|wood\s+windows?|sash\s+windows?|sash\s+(?:&|and)\s+(?:casement|alumini?um)\s+windows?|box\s+sash|sliding\s+sash|casement\s+windows?|flush\s+casement|accoya\s+windows?|hardwood\s+windows?|softwood\s+windows?|oak\s+windows?|bespoke\s+joinery|heritage\s+windows?|listed\s+building\s+windows?|conservation\s+area\s+windows?|alu[- ]?clad\s+(?:timber|windows?)|draught[- ]?proofing|holzfenster|holz-alu-fenster|fen[eê]tres?\s+bois|houten\s+kozijnen|ventanas?\s+de\s+madera|serramenti\s+in\s+legno|okna\s+drewniane)\b",
            re.I,
        ),
    ),
    (
        "aluminium",
        0.35,
        re.compile(
            r"\b(?:alumini?um\s+windows?|alumini?um\s+(?:doors?|glazing|frames?|systems?|fabricat\w+)|bi-?fold(?:ing)?\s+(?:doors?|windows?)|sliding\s+(?:patio\s+)?doors?|slimline\s+(?:alumini?um|windows?|glazing)|thermally\s+broken|smart\s+architectural\s+aluminium|aluk|reynaers|schuco|sch[uü]co|cortizo|senior\s+architectural|kawneer|origin\s+(?:windows|bifold|global)|technal|wicanders|wicona|yawal|aluprof|alufenster|aluminiumfenster|menuiserie\s+aluminium|aluminium\s+kozijnen|carpinter[ií]a\s+de\s+aluminio|ventanas?\s+de\s+aluminio|serramenti\s+in\s+alluminio|infissi\s+in\s+alluminio|okna\s+aluminiowe|esquadrias\s+de\s+alum[ií]nio)\b",
            re.I,
        ),
    ),
    (
        "steel_crittall",
        0.35,
        re.compile(
            r"\b(?:steel\s+windows?|crittall(?:\s+style|\s+windows?)?|wrought\s+iron\s+windows?|bronze\s+windows?|hot[- ]rolled\s+steel\s+windows?|heritage\s+metal\s+windows?|industrial\s+steel\s+(?:doors?|windows?|partitions?)|stahlfenster|fen[eê]tres?\s+acier|stalen\s+(?:ramen|kozijnen))\b",
            re.I,
        ),
    ),
    (
        "glass_glaziers",
        0.32,
        re.compile(
            r"\b(?:glaziers?|glazing\s+(?:company|contractor|services?|specialists?|repairs?)|emergency\s+(?:glazier|glazing|boarding)|flat\s+glass|float\s+glass|toughened\s+glass|tempered\s+glass|laminated\s+glass|annealed\s+glass|sealed\s+units?|insulated\s+glass\s+units?|igus?|glass\s+(?:merchant|supplier|processor|cutter|cutting|replacement|balustrades?|splashbacks?|partitions?|showers?)|pilkington|saint[- ]gobain|guardian\s+glass|agc\s+glass|fire[- ]rated\s+glass|acoustic\s+glass|obscure\s+glass|cut[- ]to[- ]size\s+glass|glaserei|glasermeister|vitrerie|vitrier|miroiterie|glaszetter|glashandel|vetreria|cristaler[ií]a|szklarz|vidra[cç]aria|glarmester)\b",
            re.I,
        ),
    ),
    (
        "skylights_conservatories",
        0.30,
        re.compile(
            r"\b(?:skylights?|roof\s+windows?|roof\s+lanterns?|rooflights?|flat\s+roof\s+lights?|walk[- ]on\s+glass|velux\s+(?:windows?|install\w+)|fakro|conservator(?:y|ies)|oranger(?:y|ies)|garden\s+rooms?|sunrooms?|tiled\s+conservatory\s+roof|dachfenster|lichtkuppel|fen[eê]tre\s+de\s+toit|dakraam|lichtstraat)\b",
            re.I,
        ),
    ),
    (
        "commercial_curtain_wall",
        0.35,
        re.compile(
            r"\b(?:curtain\s+wall(?:ing|s)?|fenestration|architectural\s+glazing|structural\s+glazing|planar\s+glazing|commercial\s+(?:glazing|windows?)|fa[cç]ade\s+(?:glazing|engineering|systems?)|shopfront\s+glazing|storefront\s+(?:glass|windows?)|frameless\s+glazing|unitised\s+facade)\b",
            re.I,
        ),
    ),
    (
        "manufacturers_suppliers",
        0.32,
        re.compile(
            r"\b(?:windows?\s+(?:manufactur\w+|fabricat\w+|supplier\w*|wholesal\w+|extrud\w+|hardware|ironmongery|handles?|hinges?|espags?|gaskets?|seals?)|trade\s+(?:windows?|frames?|glazing|counter|supply)|supply[- ]only\s+windows?|glass\s+(?:manufactur\w+|fabricat\w+|wholesal\w+|processor)|fensa|certass|ggf|glass\s+and\s+glazing\s+federation|nfrc|aama|fgia|wdma|bfrc|secured\s+by\s+design|pas\s*24|fensterbau|fensterhersteller|stolarka\s+okienna)\b",
            re.I,
        ),
    ),
    (
        "installers_replacement",
        0.32,
        re.compile(
            r"\b(?:replacement\s+windows?|window\s+(?:installation|installers?|fitters?|fitting|replacement|repairs?|restoration|company|contractors?|specialists?)|windows?\s+(?:&|and)\s+doors?|doors?\s+(?:&|and)\s+windows?|bay\s+windows?|bow\s+windows?|tilt\s+(?:&|and)\s+turn\s+windows?|awning\s+windows?|double[- ]hung\s+windows?|single[- ]hung\s+windows?|picture\s+windows?|egress\s+windows?|impact\s+windows?|hurricane\s+windows?|storm\s+windows?|fiberglass\s+windows?|composite\s+windows?|new\s+windows?|bespoke\s+windows?|custom\s+windows?|energy\s+star\s+windows?|pella|andersen\s+windows|marvin\s+windows|milgard|jeld-?wen|simonton|alpen\s+windows|serramenti|infissi|kozijnen|ventanas|fen[eê]tres|vinduer|f[oö]nster)\b",
            re.I,
        ),
    ),
    (
        "stained_decorative_glass",
        0.28,
        re.compile(
            r"\b(?:stained\s+glass(?:\s+windows?|\s+studio|\s+restoration)?|leaded\s+(?:glass|lights?|windows?)|bevelled\s+glass|beveled\s+glass|etched\s+glass|architectural\s+art\s+glass|vitrail|vitraux|glas[- ]in[- ]lood|bleiverglasung)\b",
            re.I,
        ),
    ),
    (
        "window_film_tinting",
        0.26,
        re.compile(
            r"\b(?:architectural\s+window\s+film|solar\s+control\s+film|privacy\s+window\s+film|security\s+window\s+film|commercial\s+window\s+tinting|residential\s+window\s+(?:tinting|film)|glass\s+manifestation|anti[- ]glare\s+film)\b",
            re.I,
        ),
    ),
    (
        "window_treatments",
        0.24,
        re.compile(
            r"\b(?:plantation\s+shutters?|window\s+shutters?|window\s+blinds?|roller\s+blinds?|venetian\s+blinds?|vertical\s+blinds?|roman\s+blinds?|integral\s+blinds?|rollladen|volets?\s+roulants?|persianas?|tapparelle)\b",
            re.I,
        ),
    ),
)

# Parked / for-sale / dead placeholder website indicators
_PARKED_HTML_RE = re.compile(
    r"(?:this\s+domain\s+(?:is\s+for\s+sale|may\s+be\s+for\s+sale|has\s+expired|is\s+parked|name\s+is\s+for\s+sale)"
    r"|buy\s+this\s+domain|domain\s+for\s+sale|inquire\s+about\s+this\s+domain|get\s+this\s+domain"
    r"|sedoparking\.com|hugedomains\.com|afternic\.com|parkingcrew\.net|bodis\.com|dan\.com/buy-domain"
    r"|godaddy\.com/forsale|sav\.com/auctions|namecheap\.com/domains/marketplace"
    r"|parked\s+(?:free\s+)?courtesy\s+of|future\s+home\s+of\s+something\s+quite\s+cool"
    r"|default\s+web\s+site\s+page|cgi-sys/defaultwebpage\.cgi|apache2\s+(?:ubuntu|debian)\s+default\s+page"
    r"|account\s+suspended|website\s+coming\s+soon\s*[-|]?\s*(?:godaddy|wix|squarespace|hostinger|bluehost))",
    re.I,
)

# URL path hints used in Common Crawl CDX and search results
_POSITIVE_PATH_RE = re.compile(
    r"/(?:double-?glazing|triple-?glazing|secondary-?glazing|upvc-?windows?|sash-?windows?|timber-?windows?"
    r"|wood(?:en)?-?windows?|alumini?um-?windows?|steel-?windows?|crittall|vinyl-?windows?|fiberglass-?windows?"
    r"|casement-?windows?|bifold-?doors?|bi-?fold-?doors?|sliding-?doors?|bay-?windows?|impact-?windows?"
    r"|hurricane-?windows?|replacement-?windows?|window-?replacement|window-?installation|window-?repair"
    r"|window-?manufactur|window-?supplier|commercial-?glazing|architectural-?glazing|structural-?glazing"
    r"|curtain-?wall(?:ing)?|fenestration|skylights?|roof-?lanterns?|roof-?windows?|rooflights?"
    r"|sealed-?units?|toughened-?glass|glaziers?|glazing-?services?|windows?-?and-?doors?"
    r"|fensterbau|glaserei|vitrerie|miroiterie|menuiserie-?alu|kozijnen|dubbelglas|serramenti|infissi|cristaleria|ventanas-?(?:pvc|aluminio)|okna-?pvc)",
    re.I,
)

# Overture / OSM / Maps explicit positive & negative category slugs
OVERTURE_CORE_WINDOW_CATEGORIES: frozenset[str] = frozenset(
    {
        "windows_installation",
        "window_installation",
        "door_and_window",
        "doors_and_windows",
        "door_sales_and_installation",
        "glass_and_mirror_shop",
        "glass_and_mirror",
        "glazier",
        "glazing",
        "glass_manufacturer",
        "glass_supplier",
        "glass_service",
        "commercial_and_industrial_glass",
        "skylight_installation",
        "sunroom_deck_and_patio_builder",
        "conservatory",
        "stained_glass",
    }
)

OVERTURE_REJECT_CATEGORIES: frozenset[str] = frozenset(
    {
        "auto_glass_service",
        "auto_glass",
        "windshield_installation_and_repair",
        "automotive_repair",
        "auto_body_shop",
        "car_wash",
        "car_dealer",
        "car_window_tinting",
        "eyewear_and_opticians",
        "optometrist",
        "ophthalmologist",
        "sunglasses_store",
        "optical_goods",
        "window_washing",
        "gutter_service",
        "pressure_washing",
        "computer_store",
        "software_development",
        "it_service_and_computer_repair",
        "electronics",
        "mobile_phone_repair",
        "telecommunications",
        "web_design",
        "internet_service_provider",
        "restaurant",
        "bar",
        "pub",
        "cafe",
        "winery",
        "brewery",
        "hotel",
        "smoke_shop",
        "vape_shop",
        "cannabis_dispensary",
        "jewelry_store",
        "beauty_salon",
        "nail_salon",
        "music_school",
        "dance_school",
        "performing_arts",
        "college_university",
        "botanical_garden",
        "boat_repair",
        "swimming_pool_contractor",
    }
)


def classify_domain_only(
    domain_or_url: str | NormalizedDomain,
    options: FilterOptions | None = None,
) -> ClassificationResult:
    """Fast lexical classification using ONLY the domain name (for 100M-domain streams & CT logs)."""
    opts = options or FilterOptions()
    norm = domain_or_url if isinstance(domain_or_url, NormalizedDomain) else normalize_url(domain_or_url)
    if norm is None:
        return ClassificationResult(False, 0.0, [], "invalid_or_blocked_domain")

    if opts.allowed_countries and norm.inferred_country and norm.inferred_country not in opts.allowed_countries:
        return ClassificationResult(False, 0.0, [], "country_filtered")

    sld = norm.sld
    full = norm.domain

    # 1. Hard reject Microsoft Windows / software / tech / adult / gambling domains
    if _MS_WINDOWS_DOMAIN_NEG_RE.search(sld):
        return ClassificationResult(False, 0.0, [], "ms_windows_or_tech_noise")

    # 2. Auto glass check (before general glass)
    if _AUTO_GLASS_RE.search(sld):
        if opts.include_auto_glass:
            return ClassificationResult(True, 0.85, ["auto_glass"], "auto_glass_included")
        return ClassificationResult(False, 0.0, [], "auto_glass_excluded")

    # 3. Non-building glass (eyewear, drinkware, smoking, lab, phone, marine, fiber optic)
    if _NON_BUILDING_GLASS_NEG_RE.search(sld):
        return ClassificationResult(False, 0.0, [], "non_building_glass_noise")

    # 4. Window cleaning check
    if _WINDOW_CLEANING_RE.search(sld):
        if opts.include_window_cleaning:
            return ClassificationResult(True, 0.88, ["window_cleaning"], "window_cleaning_included")
        return ClassificationResult(False, 0.0, [], "window_cleaning_excluded")

    # 5. Reject bare "glasses" (opticians/sunglasses/drinkware) unless explicitly stained/window glass
    if _PLURAL_GLASSES_RE.search(sld) and not re.search(r"(?:stained|leaded|window|glaz)", sld, re.I):
        return ClassificationResult(False, 0.0, [], "plural_glasses_eyewear_or_drinkware")

    # 6. Check high-precision strong window/glazing domain patterns
    cats: list[str] = []
    best_conf = 0.0
    for cat, conf, pattern in _STRONG_DOMAIN_PATTERNS:
        if cat == "stained_decorative_glass" and not opts.include_stained_glass:
            continue
        if cat == "skylights_conservatories" and not opts.include_conservatories and _BARE_CONSERVATORY_RE.search(sld):
            if "skylight" not in sld and "roof" not in sld and "lantern" not in sld:
                continue
        if pattern.search(sld):
            # Guard conservatory against music/dance/botanical
            if cat == "skylights_conservatories" and _BARE_CONSERVATORY_RE.search(sld):
                if _NON_BUILDING_CONSERVATORY_NEG_RE.search(sld):
                    return ClassificationResult(False, 0.0, [], "non_building_conservatory")
            if cat not in cats:
                cats.append(cat)
            if conf > best_conf:
                best_conf = conf

    # 7. Window film / tinting
    if _WINDOW_TINT_RE.search(sld):
        if opts.include_tinting:
            if "window_film_tinting" not in cats:
                cats.append("window_film_tinting")
            best_conf = max(best_conf, 0.82)
        elif not cats:
            return ClassificationResult(False, 0.0, [], "window_tinting_excluded")

    # 8. .glass gTLD (e.g. apex.glass, london.glass — almost always architectural/glazing after negative filter!)
    if norm.suffix == "glass" and not cats:
        cats.append("glass_glaziers")
        best_conf = max(best_conf, 0.80)

    # 9. Multilingual window domains (e.g. mueller-fenster.de, paris-fenetres.fr, madrid-ventanas.es)
    if _MULTILINGUAL_WINDOW_DOMAIN_RE.search(sld) and not cats:
        cats.append("general_windows")
        best_conf = max(best_conf, 0.84)

    # 10. Window treatments (shutters/blinds)
    has_treatment = bool(_WINDOW_TREATMENT_ONLY_RE.search(sld))
    if has_treatment and not cats:
        if opts.include_treatments or (_BARE_WINDOW_RE.search(sld) and "blind" not in sld):
            cats.append("window_treatments")
            best_conf = max(best_conf, 0.78)
        else:
            return ClassificationResult(False, 0.0, [], "window_treatments_excluded")

    # 11. General "window"/"windows" business domains (e.g. anglianwindows.co.uk, acme-windows.com, premierwindow.ca)
    if not cats and _BARE_WINDOW_RE.search(sld):
        # Extra guard: very short/generic tech-ish suffixes (.io, .dev, .app, .ai, .tech, .cloud, .gg, .xyz, .top)
        if norm.suffix in ("io", "dev", "app", "ai", "tech", "cloud", "software", "codes", "gg", "tv", "fm", "xyz", "top", "icu", "vip", "club", "fun", "online", "site"):
            return ClassificationResult(False, 0.0, [], "ambiguous_window_on_tech_tld")
        # Plural "windows" on commercial/country TLDs is overwhelmingly fenestration once MS-Windows terms are removed
        is_plural = "windows" in sld
        is_local_cctld = norm.inferred_country in ("GB", "IE", "AU", "NZ", "CA", "US", "ZA")
        conf = 0.78 if (is_plural and is_local_cctld) else (0.74 if is_plural else 0.68)
        cats.append("general_windows")
        best_conf = max(best_conf, conf)

    # 12. General "glass" business domains (e.g. midlandglass.co.uk, cityglass.com, acme-glass.com.au)
    if not cats and _BARE_GLASS_RE.search(sld):
        if norm.suffix in ("io", "dev", "app", "ai", "tech", "gg", "tv", "fm", "xyz", "top", "icu", "org", "edu"):
            return ClassificationResult(False, 0.0, [], "ambiguous_glass_tld")
        is_local_cctld = norm.inferred_country in ("GB", "IE", "AU", "NZ", "CA", "US", "ZA")
        conf = 0.72 if is_local_cctld else 0.66
        cats.append("glass_glaziers")
        best_conf = max(best_conf, conf)

    # 13. UK/IE standalone "conservatories" domains (e.g. hertsconservatories.co.uk)
    if not cats and opts.include_conservatories and _BARE_CONSERVATORY_RE.search(sld):
        if _NON_BUILDING_CONSERVATORY_NEG_RE.search(sld):
            return ClassificationResult(False, 0.0, [], "non_building_conservatory")
        if norm.inferred_country in ("GB", "IE") or "conservatories" in sld:
            cats.append("skylights_conservatories")
            best_conf = max(best_conf, 0.76)

    if not cats or best_conf < opts.min_confidence:
        return ClassificationResult(False, best_conf, cats, f"no_window_signal:{full}")

    return ClassificationResult(True, round(min(best_conf, 0.99), 3), cats, "domain_match")


def classify_candidate(
    url: str,
    *,
    business_name: str = "",
    title: str = "",
    snippet: str = "",
    category_hint: str = "",
    source_trust: str = "medium",  # "high" (OSM/Overture glazing POI), "medium" (Maps/YP/CDX), "low" (web search)
    options: FilterOptions | None = None,
) -> tuple[NormalizedDomain | None, ClassificationResult]:
    """Classify a candidate URL using all available context (domain + path + name + title + snippet + POI category)."""
    opts = options or FilterOptions()
    norm = normalize_url(url)
    if norm is None:
        return None, ClassificationResult(False, 0.0, [], "invalid_or_blocked_domain")

    if opts.allowed_countries and norm.inferred_country and norm.inferred_country not in opts.allowed_countries:
        return norm, ClassificationResult(False, 0.0, [], "country_filtered")

    combined_text = " ".join(
        part for part in (business_name, title, snippet, category_hint, norm.original_path.replace("/", " ").replace("-", " ")) if part
    ).strip()

    # Fast domain check first
    dom_res = classify_domain_only(
        norm,
        FilterOptions(
            min_confidence=0.50,
            include_treatments=opts.include_treatments,
            include_tinting=opts.include_tinting,
            include_stained_glass=opts.include_stained_glass,
            include_conservatories=opts.include_conservatories,
            include_window_cleaning=opts.include_window_cleaning,
            include_auto_glass=opts.include_auto_glass,
        ),
    )
    if dom_res.reason in ("ms_windows_or_tech_noise", "non_building_glass_noise", "plural_glasses_eyewear_or_drinkware", "non_building_conservatory"):
        return norm, dom_res
    if dom_res.reason == "auto_glass_excluded" and not opts.include_auto_glass:
        return norm, dom_res
    if dom_res.reason == "window_cleaning_excluded" and not opts.include_window_cleaning:
        return norm, dom_res

    # Check text-level hard negatives (catches e.g. techblog.com talking about Windows 11)
    if combined_text:
        if _MS_WINDOWS_TEXT_NEG_RE.search(combined_text):
            return norm, ClassificationResult(False, 0.0, [], "ms_windows_text_noise")
        if _NON_WINDOW_TEXT_NEG_RE.search(combined_text):
            return norm, ClassificationResult(False, 0.0, [], "non_window_text_noise")

    # Gather text-level positive categories
    cats: list[str] = list(dom_res.categories)
    text_score = 0.0
    if combined_text:
        for cat, weight, pattern in _POSITIVE_TEXT_CATEGORY_RES:
            if cat == "window_treatments" and not opts.include_treatments and not cats:
                continue
            if cat == "window_film_tinting" and not opts.include_tinting:
                continue
            if cat == "stained_decorative_glass" and not opts.include_stained_glass:
                continue
            if pattern.search(combined_text):
                if cat not in cats:
                    cats.append(cat)
                text_score += weight

    # Check auto-glass / window-cleaning text when no core window manufacturing/installation category matched
    core_cats = [c for c in cats if c not in ("auto_glass", "window_cleaning", "window_treatments", "window_film_tinting")]
    if combined_text and _AUTO_GLASS_TEXT_RE.search(combined_text) and not core_cats:
        if opts.include_auto_glass:
            return norm, ClassificationResult(True, 0.84, ["auto_glass"], "auto_glass_text_included")
        return norm, ClassificationResult(False, 0.0, [], "auto_glass_text_excluded")

    if combined_text and _WINDOW_CLEANING_TEXT_RE.search(combined_text) and not core_cats:
        if opts.include_window_cleaning:
            return norm, ClassificationResult(True, 0.85, ["window_cleaning"], "window_cleaning_text_included")
        return norm, ClassificationResult(False, 0.0, [], "window_cleaning_text_excluded")

    # Check structured POI category hint (Overture / OSM / Google Maps / YellowPages)
    cat_slug = category_hint.strip().lower().replace(" ", "_").replace("-", "_")
    if cat_slug in OVERTURE_REJECT_CATEGORIES and not core_cats:
        if "auto_glass" in cat_slug or "windshield" in cat_slug:
            if opts.include_auto_glass:
                return norm, ClassificationResult(True, 0.85, ["auto_glass"], "poi_auto_glass")
        if "window_washing" in cat_slug and opts.include_window_cleaning:
            return norm, ClassificationResult(True, 0.85, ["window_cleaning"], "poi_window_cleaning")
        return norm, ClassificationResult(False, 0.0, [], f"rejected_poi_category:{cat_slug}")

    # URL path signal (e.g. smithjoinery.co.uk/timber-windows -> strong real business signal!)
    if _POSITIVE_PATH_RE.search(norm.original_path):
        text_score += 0.35
        if not cats:
            cats.append("general_windows")

    # Compute final confidence based on source trust + domain signal + text signal
    base_by_trust = {"high": 0.82, "medium": 0.65, "low": 0.35}
    base = base_by_trust.get(source_trust, 0.55)

    if source_trust == "high":
        # Curated POI categories (craft=glazier, shop=windows, windows_installation)
        conf = max(base, dom_res.confidence) + min(0.15, text_score * 0.4)
        if not cats:
            if "glaz" in cat_slug or "glass" in cat_slug:
                cats.append("glass_glaziers")
            else:
                cats.append("general_windows")
    elif source_trust == "medium":
        # Google Maps / YellowPages / Common Crawl CDX targeted query results
        if dom_res.accepted:
            conf = max(dom_res.confidence, 0.78) + min(0.18, text_score * 0.4)
        elif text_score >= 0.25:
            conf = base + min(0.30, text_score * 0.6)
        else:
            # Business like "Pella Corp" or "Smith & Sons Ltd" returned by Google Maps for "double glazing"
            conf = base
            if not cats:
                cats.append("general_windows")
    else:
        # Broad organic web search: require EITHER a strong domain match OR real window text signals
        if dom_res.accepted and text_score >= 0.25:
            conf = min(0.97, max(dom_res.confidence, 0.80) + min(0.16, text_score * 0.35))
        elif dom_res.accepted:
            conf = dom_res.confidence
        elif text_score >= 0.30:
            conf = min(0.92, 0.48 + text_score * 0.65)
        else:
            return norm, ClassificationResult(False, round(base, 3), cats, "insufficient_web_signal")

    conf = round(min(0.99, conf), 3)
    if conf < opts.min_confidence:
        return norm, ClassificationResult(False, conf, cats, "below_min_confidence")

    if not cats:
        cats.append("general_windows")
    return norm, ClassificationResult(True, conf, cats, "candidate_match")


def classify_html(
    url: str,
    html: str,
    options: FilterOptions | None = None,
) -> tuple[ClassificationResult, str, str, bool]:
    """Analyze a fetched homepage's HTML to verify it is a live, non-parked window/glazing business.

    Returns: (ClassificationResult, page_title, meta_description, is_parked)
    """
    opts = options or FilterOptions()
    snippet_html = html[:200_000]  # Bound parsing time on huge pages

    try:
        soup = BeautifulSoup(snippet_html, "lxml")
    except Exception:
        soup = BeautifulSoup(snippet_html, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())[:300]

    meta_desc = ""
    for attrs in (
        {"name": re.compile(r"^description$", re.I)},
        {"property": re.compile(r"^og:description$", re.I)},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            meta_desc = " ".join(str(tag["content"]).split())[:500]
            if meta_desc:
                break

    if not title:
        og_t = soup.find("meta", attrs={"property": re.compile(r"^og:title$", re.I)})
        if og_t and og_t.get("content"):
            title = " ".join(str(og_t["content"]).split())[:300]

    # Collect headings and a bounded body excerpt
    headings = " ".join(
        " ".join(h.get_text(" ", strip=True).split())
        for h in soup.find_all(["h1", "h2", "h3"], limit=25)
    )[:2000]

    # Remove script/style before sampling visible text
    for bad in soup.find_all(["script", "style", "noscript"]):
        bad.decompose()
    body_text = " ".join(soup.get_text(" ", strip=True).split())[:8000]

    # Detect parked / for-sale / default server pages
    parked_probe = f"{title} {meta_desc} {headings} {snippet_html[:8000]}"
    if len(body_text) < 900 and _PARKED_HTML_RE.search(parked_probe):
        return ClassificationResult(False, 0.0, [], "parked_domain"), title, meta_desc, True
    if _PARKED_HTML_RE.search(f"{title} {meta_desc}"):
        return ClassificationResult(False, 0.0, [], "parked_domain"), title, meta_desc, True

    header_text = f"{title} {meta_desc} {headings}"
    full_text = f"{header_text} {body_text}"

    # Reject Microsoft Windows / eyewear / smoking / music conservatory pages
    if _MS_WINDOWS_TEXT_NEG_RE.search(header_text):
        return ClassificationResult(False, 0.0, [], "ms_windows_html"), title, meta_desc, False
    if _NON_WINDOW_TEXT_NEG_RE.search(header_text):
        return ClassificationResult(False, 0.0, [], "non_window_html"), title, meta_desc, False

    cats: list[str] = []
    score = 0.0
    for cat, weight, pattern in _POSITIVE_TEXT_CATEGORY_RES:
        if cat == "window_treatments" and not opts.include_treatments:
            continue
        if cat == "window_film_tinting" and not opts.include_tinting:
            continue
        if cat == "stained_decorative_glass" and not opts.include_stained_glass:
            continue
        if pattern.search(header_text):
            cats.append(cat)
            score += weight * 1.4
        elif pattern.search(body_text):
            cats.append(cat)
            score += weight * 0.85

    core_cats = [c for c in cats if c not in ("auto_glass", "window_cleaning", "window_treatments", "window_film_tinting")]

    if _AUTO_GLASS_TEXT_RE.search(header_text) and not core_cats:
        if opts.include_auto_glass:
            return ClassificationResult(True, 0.88, ["auto_glass"], "verified_auto_glass"), title, meta_desc, False
        return ClassificationResult(False, 0.0, [], "auto_glass_html"), title, meta_desc, False

    if _WINDOW_CLEANING_TEXT_RE.search(header_text) and not core_cats:
        if opts.include_window_cleaning:
            return ClassificationResult(True, 0.88, ["window_cleaning"], "verified_window_cleaning"), title, meta_desc, False
        return ClassificationResult(False, 0.0, [], "window_cleaning_html"), title, meta_desc, False

    # Check body for MS Windows if score is weak
    if score < 0.45 and _MS_WINDOWS_TEXT_NEG_RE.search(full_text):
        return ClassificationResult(False, 0.0, [], "ms_windows_body"), title, meta_desc, False

    dom_res = classify_domain_only(url, opts)
    if dom_res.accepted:
        score += 0.25
        for c in dom_res.categories:
            if c not in cats:
                cats.append(c)

    if score >= 0.35:
        conf = round(min(0.99, 0.50 + score * 0.55), 3)
        return ClassificationResult(True, conf, cats or ["general_windows"], "verified_html"), title, meta_desc, False

    return ClassificationResult(False, round(min(0.49, score), 3), cats, "no_window_content_on_page"), title, meta_desc, False
