"""Global geographic grid, UK postcode generator, custom location loader, and adaptive quadtree tiler."""

from __future__ import annotations

import csv
from pathlib import Path

from window_harvester.models import BoundingBox, GeoLocation

# ---------------------------------------------------------------------------
# 1. UNITED KINGDOM — Cities, London Boroughs, Towns, Counties & Postcode Areas
# ---------------------------------------------------------------------------

UK_TIER1_CITIES: tuple[tuple[str, str], ...] = (
    # Major UK cities
    ("London", "Greater London"),
    ("Birmingham", "West Midlands"),
    ("Manchester", "Greater Manchester"),
    ("Leeds", "West Yorkshire"),
    ("Glasgow", "Scotland"),
    ("Liverpool", "Merseyside"),
    ("Bristol", "Bristol"),
    ("Sheffield", "South Yorkshire"),
    ("Edinburgh", "Scotland"),
    ("Leicester", "Leicestershire"),
    ("Coventry", "West Midlands"),
    ("Bradford", "West Yorkshire"),
    ("Cardiff", "Wales"),
    ("Belfast", "Northern Ireland"),
    ("Nottingham", "Nottinghamshire"),
    ("Kingston upon Hull", "East Yorkshire"),
    ("Newcastle upon Tyne", "Tyne and Wear"),
    ("Stoke-on-Trent", "Staffordshire"),
    ("Southampton", "Hampshire"),
    ("Derby", "Derbyshire"),
    ("Portsmouth", "Hampshire"),
    ("Brighton", "East Sussex"),
    ("Plymouth", "Devon"),
    ("Wolverhampton", "West Midlands"),
    ("Reading", "Berkshire"),
    ("Aberdeen", "Scotland"),
    ("Bournemouth", "Dorset"),
    ("Norwich", "Norfolk"),
    ("Luton", "Bedfordshire"),
    ("Swindon", "Wiltshire"),
    ("Milton Keynes", "Buckinghamshire"),
    ("Northampton", "Northamptonshire"),
    ("Southend-on-Sea", "Essex"),
    ("Warrington", "Cheshire"),
    ("Peterborough", "Cambridgeshire"),
    ("Sunderland", "Tyne and Wear"),
    ("Oxford", "Oxfordshire"),
    ("Cambridge", "Cambridgeshire"),
    ("York", "North Yorkshire"),
    ("Slough", "Berkshire"),
    ("Ipswich", "Suffolk"),
    ("Middlesbrough", "North Yorkshire"),
    ("Bolton", "Greater Manchester"),
    ("Stockport", "Greater Manchester"),
    ("Blackpool", "Lancashire"),
    ("Huddersfield", "West Yorkshire"),
    ("Swansea", "Wales"),
    ("Dundee", "Scotland"),
    ("Gloucester", "Gloucestershire"),
    ("Exeter", "Devon"),
    ("Chelmsford", "Essex"),
    ("Colchester", "Essex"),
    ("Basildon", "Essex"),
    ("Crawley", "West Sussex"),
    ("Watford", "Hertfordshire"),
    ("St Albans", "Hertfordshire"),
    ("Preston", "Lancashire"),
    ("Blackburn", "Lancashire"),
    ("Oldham", "Greater Manchester"),
    ("Rochdale", "Greater Manchester"),
    ("Salford", "Greater Manchester"),
    ("Wigan", "Greater Manchester"),
    ("Rotherham", "South Yorkshire"),
    ("Doncaster", "South Yorkshire"),
    ("Barnsley", "South Yorkshire"),
    ("Wakefield", "West Yorkshire"),
    ("Halifax", "West Yorkshire"),
    ("Walsall", "West Midlands"),
    ("Dudley", "West Midlands"),
    ("West Bromwich", "West Midlands"),
    ("Solihull", "West Midlands"),
    ("Telford", "Shropshire"),
    ("Worcester", "Worcestershire"),
    ("Lincoln", "Lincolnshire"),
    ("Chester", "Cheshire"),
    ("Bath", "Somerset"),
    ("Maidstone", "Kent"),
    ("Canterbury", "Kent"),
    ("Guildford", "Surrey"),
    ("Basingstoke", "Hampshire"),
    ("Newport", "Wales"),
    ("Wrexham", "Wales"),
    ("Inverness", "Scotland"),
    ("Derry", "Northern Ireland"),
    # All 32 London Boroughs (London alone has thousands of window/glazing businesses)
    ("Croydon", "London"),
    ("Barnet", "London"),
    ("Ealing", "London"),
    ("Enfield", "London"),
    ("Bromley", "London"),
    ("Brent", "London"),
    ("Wandsworth", "London"),
    ("Lambeth", "London"),
    ("Southwark", "London"),
    ("Lewisham", "London"),
    ("Greenwich", "London"),
    ("Bexley", "London"),
    ("Havering", "London"),
    ("Romford", "London"),
    ("Redbridge", "London"),
    ("Ilford", "London"),
    ("Newham", "London"),
    ("Waltham Forest", "London"),
    ("Haringey", "London"),
    ("Hackney", "London"),
    ("Tower Hamlets", "London"),
    ("Islington", "London"),
    ("Camden", "London"),
    ("Westminster", "London"),
    ("Kensington and Chelsea", "London"),
    ("Hammersmith and Fulham", "London"),
    ("Hounslow", "London"),
    ("Richmond upon Thames", "London"),
    ("Kingston upon Thames", "London"),
    ("Merton", "London"),
    ("Wimbledon", "London"),
    ("Sutton", "London"),
    ("Harrow", "London"),
    ("Hillingdon", "London"),
    ("Uxbridge", "London"),
)

UK_TIER2_TOWNS: tuple[tuple[str, str], ...] = (
    # Hertfordshire, Beds, Bucks, Berks, Oxon
    ("Welwyn Garden City", "Hertfordshire"),
    ("Hatfield", "Hertfordshire"),
    ("Stevenage", "Hertfordshire"),
    ("Hemel Hempstead", "Hertfordshire"),
    ("Hertford", "Hertfordshire"),
    ("Hitchin", "Hertfordshire"),
    ("Letchworth", "Hertfordshire"),
    ("Bishops Stortford", "Hertfordshire"),
    ("Borehamwood", "Hertfordshire"),
    ("Potters Bar", "Hertfordshire"),
    ("Cheshunt", "Hertfordshire"),
    ("Harpenden", "Hertfordshire"),
    ("Berkhamsted", "Hertfordshire"),
    ("Rickmansworth", "Hertfordshire"),
    ("Bedford", "Bedfordshire"),
    ("Dunstable", "Bedfordshire"),
    ("Leighton Buzzard", "Bedfordshire"),
    ("Biggleswade", "Bedfordshire"),
    ("High Wycombe", "Buckinghamshire"),
    ("Aylesbury", "Buckinghamshire"),
    ("Amersham", "Buckinghamshire"),
    ("Chesham", "Buckinghamshire"),
    ("Marlow", "Buckinghamshire"),
    ("Bracknell", "Berkshire"),
    ("Maidenhead", "Berkshire"),
    ("Wokingham", "Berkshire"),
    ("Newbury", "Berkshire"),
    ("Windsor", "Berkshire"),
    ("Banbury", "Oxfordshire"),
    ("Bicester", "Oxfordshire"),
    ("Abingdon", "Oxfordshire"),
    ("Didcot", "Oxfordshire"),
    ("Witney", "Oxfordshire"),
    # South East — Kent, Surrey, Sussex, Hampshire
    ("Dartford", "Kent"),
    ("Gravesend", "Kent"),
    ("Gillingham", "Kent"),
    ("Chatham", "Kent"),
    ("Rochester", "Kent"),
    ("Sittingbourne", "Kent"),
    ("Ashford", "Kent"),
    ("Folkestone", "Kent"),
    ("Dover", "Kent"),
    ("Margate", "Kent"),
    ("Ramsgate", "Kent"),
    ("Tunbridge Wells", "Kent"),
    ("Tonbridge", "Kent"),
    ("Sevenoaks", "Kent"),
    ("Woking", "Surrey"),
    ("Farnborough", "Hampshire"),
    ("Aldershot", "Hampshire"),
    ("Epsom", "Surrey"),
    ("Redhill", "Surrey"),
    ("Reigate", "Surrey"),
    ("Camberley", "Surrey"),
    ("Staines", "Surrey"),
    ("Walton-on-Thames", "Surrey"),
    ("Weybridge", "Surrey"),
    ("Leatherhead", "Surrey"),
    ("Dorking", "Surrey"),
    ("Farnham", "Surrey"),
    ("Worthing", "West Sussex"),
    ("Chichester", "West Sussex"),
    ("Horsham", "West Sussex"),
    ("Bognor Regis", "West Sussex"),
    ("Haywards Heath", "West Sussex"),
    ("Burgess Hill", "West Sussex"),
    ("East Grinstead", "West Sussex"),
    ("Eastbourne", "East Sussex"),
    ("Hastings", "East Sussex"),
    ("Bexhill", "East Sussex"),
    ("Lewes", "East Sussex"),
    ("Winchester", "Hampshire"),
    ("Eastleigh", "Hampshire"),
    ("Fareham", "Hampshire"),
    ("Gosport", "Hampshire"),
    ("Havant", "Hampshire"),
    ("Waterlooville", "Hampshire"),
    ("Andover", "Hampshire"),
    ("Isle of Wight", "Hampshire"),
    # East of England — Essex, Suffolk, Norfolk, Cambs
    ("Harlow", "Essex"),
    ("Brentwood", "Essex"),
    ("Grays", "Essex"),
    ("Thurrock", "Essex"),
    ("Braintree", "Essex"),
    ("Clacton-on-Sea", "Essex"),
    ("Billericay", "Essex"),
    ("Wickford", "Essex"),
    ("Rayleigh", "Essex"),
    ("Canvey Island", "Essex"),
    ("Loughton", "Essex"),
    ("Saffron Walden", "Essex"),
    ("Maldon", "Essex"),
    ("Bury St Edmunds", "Suffolk"),
    ("Lowestoft", "Suffolk"),
    ("Haverhill", "Suffolk"),
    ("Sudbury", "Suffolk"),
    ("Felixstowe", "Suffolk"),
    ("Kings Lynn", "Norfolk"),
    ("Great Yarmouth", "Norfolk"),
    ("Thetford", "Norfolk"),
    ("Huntingdon", "Cambridgeshire"),
    ("St Neots", "Cambridgeshire"),
    ("Wisbech", "Cambridgeshire"),
    ("Ely", "Cambridgeshire"),
    # South West
    ("Poole", "Dorset"),
    ("Christchurch", "Dorset"),
    ("Weymouth", "Dorset"),
    ("Dorchester", "Dorset"),
    ("Cheltenham", "Gloucestershire"),
    ("Stroud", "Gloucestershire"),
    ("Cirencester", "Gloucestershire"),
    ("Tewkesbury", "Gloucestershire"),
    ("Taunton", "Somerset"),
    ("Weston-super-Mare", "Somerset"),
    ("Yeovil", "Somerset"),
    ("Bridgwater", "Somerset"),
    ("Salisbury", "Wiltshire"),
    ("Trowbridge", "Wiltshire"),
    ("Chippenham", "Wiltshire"),
    ("Torquay", "Devon"),
    ("Paignton", "Devon"),
    ("Newton Abbot", "Devon"),
    ("Barnstaple", "Devon"),
    ("Exmouth", "Devon"),
    ("Truro", "Cornwall"),
    ("St Austell", "Cornwall"),
    ("Falmouth", "Cornwall"),
    ("Newquay", "Cornwall"),
    ("Penzance", "Cornwall"),
    # Midlands
    ("Sutton Coldfield", "West Midlands"),
    ("Stourbridge", "West Midlands"),
    ("Halesowen", "West Midlands"),
    ("Nuneaton", "Warwickshire"),
    ("Rugby", "Warwickshire"),
    ("Royal Leamington Spa", "Warwickshire"),
    ("Warwick", "Warwickshire"),
    ("Stratford-upon-Avon", "Warwickshire"),
    ("Redditch", "Worcestershire"),
    ("Kidderminster", "Worcestershire"),
    ("Bromsgrove", "Worcestershire"),
    ("Hereford", "Herefordshire"),
    ("Shrewsbury", "Shropshire"),
    ("Oswestry", "Shropshire"),
    ("Stafford", "Staffordshire"),
    ("Burton upon Trent", "Staffordshire"),
    ("Tamworth", "Staffordshire"),
    ("Cannock", "Staffordshire"),
    ("Lichfield", "Staffordshire"),
    ("Newcastle-under-Lyme", "Staffordshire"),
    ("Loughborough", "Leicestershire"),
    ("Hinckley", "Leicestershire"),
    ("Coalville", "Leicestershire"),
    ("Melton Mowbray", "Leicestershire"),
    ("Kettering", "Northamptonshire"),
    ("Corby", "Northamptonshire"),
    ("Wellingborough", "Northamptonshire"),
    ("Daventry", "Northamptonshire"),
    ("Chesterfield", "Derbyshire"),
    ("Ilkeston", "Derbyshire"),
    ("Mansfield", "Nottinghamshire"),
    ("Newark-on-Trent", "Nottinghamshire"),
    ("Worksop", "Nottinghamshire"),
    ("Grantham", "Lincolnshire"),
    ("Boston", "Lincolnshire"),
    ("Spalding", "Lincolnshire"),
    ("Scunthorpe", "Lincolnshire"),
    ("Grimsby", "Lincolnshire"),
    # North West, Yorkshire & North East
    ("Bury", "Greater Manchester"),
    ("Tameside", "Greater Manchester"),
    ("Ashton-under-Lyne", "Greater Manchester"),
    ("Altrincham", "Greater Manchester"),
    ("Sale", "Greater Manchester"),
    ("Birkenhead", "Merseyside"),
    ("Wirral", "Merseyside"),
    ("St Helens", "Merseyside"),
    ("Southport", "Merseyside"),
    ("Bootle", "Merseyside"),
    ("Crewe", "Cheshire"),
    ("Macclesfield", "Cheshire"),
    ("Ellesmere Port", "Cheshire"),
    ("Runcorn", "Cheshire"),
    ("Widnes", "Cheshire"),
    ("Northwich", "Cheshire"),
    ("Burnley", "Lancashire"),
    ("Lancaster", "Lancashire"),
    ("Morecambe", "Lancashire"),
    ("Chorley", "Lancashire"),
    ("Leyland", "Lancashire"),
    ("Accrington", "Lancashire"),
    ("Lytham St Annes", "Lancashire"),
    ("Carlisle", "Cumbria"),
    ("Barrow-in-Furness", "Cumbria"),
    ("Kendal", "Cumbria"),
    ("Harrogate", "North Yorkshire"),
    ("Scarborough", "North Yorkshire"),
    ("Northallerton", "North Yorkshire"),
    ("Keighley", "West Yorkshire"),
    ("Dewsbury", "West Yorkshire"),
    ("Batley", "West Yorkshire"),
    ("Castleford", "West Yorkshire"),
    ("Pontefract", "West Yorkshire"),
    ("Beverley", "East Yorkshire"),
    ("Bridlington", "East Yorkshire"),
    ("Gateshead", "Tyne and Wear"),
    ("South Shields", "Tyne and Wear"),
    ("North Shields", "Tyne and Wear"),
    ("Washington", "Tyne and Wear"),
    ("Durham", "County Durham"),
    ("Darlington", "County Durham"),
    ("Hartlepool", "County Durham"),
    ("Stockton-on-Tees", "County Durham"),
    ("Redcar", "North Yorkshire"),
    ("Cramlington", "Northumberland"),
    ("Blyth", "Northumberland"),
    # Scotland, Wales & Northern Ireland
    ("Paisley", "Scotland"),
    ("East Kilbride", "Scotland"),
    ("Livingston", "Scotland"),
    ("Hamilton", "Scotland"),
    ("Cumbernauld", "Scotland"),
    ("Dunfermline", "Scotland"),
    ("Kirkcaldy", "Scotland"),
    ("Ayr", "Scotland"),
    ("Perth", "Scotland"),
    ("Kilmarnock", "Scotland"),
    ("Coatbridge", "Scotland"),
    ("Greenock", "Scotland"),
    ("Glenrothes", "Scotland"),
    ("Stirling", "Scotland"),
    ("Airdrie", "Scotland"),
    ("Falkirk", "Scotland"),
    ("Motherwell", "Scotland"),
    ("Dumfries", "Scotland"),
    ("Bridgend", "Wales"),
    ("Barry", "Wales"),
    ("Neath", "Wales"),
    ("Port Talbot", "Wales"),
    ("Cwmbran", "Wales"),
    ("Llanelli", "Wales"),
    ("Caerphilly", "Wales"),
    ("Merthyr Tydfil", "Wales"),
    ("Rhyl", "Wales"),
    ("Colwyn Bay", "Wales"),
    ("Bangor", "Wales"),
    ("Carmarthen", "Wales"),
    ("Haverfordwest", "Wales"),
    ("Aberystwyth", "Wales"),
    ("Lisburn", "Northern Ireland"),
    ("Newtownabbey", "Northern Ireland"),
    ("Bangor", "Northern Ireland"),
    ("Craigavon", "Northern Ireland"),
    ("Ballymena", "Northern Ireland"),
    ("Newry", "Northern Ireland"),
    ("Carrickfergus", "Northern Ireland"),
    ("Coleraine", "Northern Ireland"),
    ("Omagh", "Northern Ireland"),
    ("Enniskillen", "Northern Ireland"),
)

# All 121 official UK postcode areas (Tier 3 exhaustive postcode sweep)
UK_POSTCODE_AREAS: tuple[str, ...] = (
    "AB", "AL", "B", "BA", "BB", "BD", "BH", "BL", "BN", "BR", "BS", "BT",
    "CA", "CB", "CF", "CH", "CM", "CO", "CR", "CT", "CV", "CW", "DA", "DD",
    "DE", "DG", "DH", "DL", "DN", "DT", "DY", "E", "EC", "EH", "EN", "EX",
    "FK", "FY", "G", "GL", "GU", "HA", "HD", "HG", "HP", "HR", "HS", "HU",
    "HX", "IG", "IP", "IV", "KA", "KT", "KW", "KY", "L", "LA", "LD", "LE",
    "LL", "LN", "LS", "LU", "M", "ME", "MK", "ML", "N", "NE", "NG", "NN",
    "NP", "NR", "NW", "OL", "OX", "PA", "PE", "PH", "PL", "PO", "PR", "RG",
    "RH", "RM", "S", "SA", "SE", "SG", "SK", "SL", "SM", "SN", "SO", "SP",
    "SR", "SS", "ST", "SW", "SY", "TA", "TD", "TF", "TN", "TQ", "TR", "TS",
    "TW", "UB", "W", "WA", "WC", "WD", "WF", "WN", "WR", "WS", "WV", "YO",
    "ZE",
)

# ---------------------------------------------------------------------------
# 2. UNITED STATES — All 50 States (Tier 1 Metros + Tier 2 Regional Cities)
# ---------------------------------------------------------------------------

US_TIER1_CITIES: tuple[tuple[str, str], ...] = (
    ("New York", "NY"), ("Los Angeles", "CA"), ("Chicago", "IL"), ("Houston", "TX"),
    ("Phoenix", "AZ"), ("Philadelphia", "PA"), ("San Antonio", "TX"), ("San Diego", "CA"),
    ("Dallas", "TX"), ("Jacksonville", "FL"), ("Austin", "TX"), ("Fort Worth", "TX"),
    ("San Jose", "CA"), ("Columbus", "OH"), ("Charlotte", "NC"), ("Indianapolis", "IN"),
    ("San Francisco", "CA"), ("Seattle", "WA"), ("Denver", "CO"), ("Oklahoma City", "OK"),
    ("Nashville", "TN"), ("Washington", "DC"), ("El Paso", "TX"), ("Las Vegas", "NV"),
    ("Boston", "MA"), ("Detroit", "MI"), ("Louisville", "KY"), ("Portland", "OR"),
    ("Memphis", "TN"), ("Baltimore", "MD"), ("Milwaukee", "WI"), ("Albuquerque", "NM"),
    ("Tucson", "AZ"), ("Fresno", "CA"), ("Sacramento", "CA"), ("Kansas City", "MO"),
    ("Mesa", "AZ"), ("Atlanta", "GA"), ("Omaha", "NE"), ("Colorado Springs", "CO"),
    ("Raleigh", "NC"), ("Long Beach", "CA"), ("Virginia Beach", "VA"), ("Miami", "FL"),
    ("Oakland", "CA"), ("Minneapolis", "MN"), ("Tulsa", "OK"), ("Bakersfield", "CA"),
    ("Tampa", "FL"), ("Wichita", "KS"), ("Arlington", "TX"), ("Aurora", "CO"),
    ("New Orleans", "LA"), ("Cleveland", "OH"), ("Anaheim", "CA"), ("Honolulu", "HI"),
    ("Henderson", "NV"), ("Orlando", "FL"), ("Lexington", "KY"), ("Stockton", "CA"),
    ("Riverside", "CA"), ("Corpus Christi", "TX"), ("Irvine", "CA"), ("Cincinnati", "OH"),
    ("Santa Ana", "CA"), ("Newark", "NJ"), ("Saint Paul", "MN"), ("Pittsburgh", "PA"),
    ("Greensboro", "NC"), ("St. Louis", "MO"), ("Lincoln", "NE"), ("Plano", "TX"),
    ("Anchorage", "AK"), ("Durham", "NC"), ("Jersey City", "NJ"), ("Chandler", "AZ"),
    ("Chula Vista", "CA"), ("Buffalo", "NY"), ("North Las Vegas", "NV"), ("Gilbert", "AZ"),
    ("Madison", "WI"), ("Reno", "NV"), ("Toledo", "OH"), ("Fort Wayne", "IN"),
    ("Lubbock", "TX"), ("St. Petersburg", "FL"), ("Laredo", "TX"), ("Irving", "TX"),
    ("Chesapeake", "VA"), ("Glendale", "AZ"), ("Winston-Salem", "NC"), ("Scottsdale", "AZ"),
    ("Garland", "TX"), ("Boise", "ID"), ("Norfolk", "VA"), ("Spokane", "WA"),
    ("Richmond", "VA"), ("Fremont", "CA"), ("Huntsville", "AL"), ("Tacoma", "WA"),
    ("Baton Rouge", "LA"), ("Des Moines", "IA"), ("Salt Lake City", "UT"), ("Birmingham", "AL"),
    ("Little Rock", "AR"), ("Hartford", "CT"), ("Wilmington", "DE"), ("Fort Lauderdale", "FL"),
    ("West Palm Beach", "FL"), ("Savannah", "GA"), ("Grand Rapids", "MI"), ("Jackson", "MS"),
    ("Billings", "MT"), ("Manchester", "NH"), ("Fargo", "ND"), ("Providence", "RI"),
    ("Charleston", "SC"), ("Columbia", "SC"), ("Sioux Falls", "SD"), ("Burlington", "VT"),
    ("Charleston", "WV"), ("Cheyenne", "WY"), ("Portland", "ME"),
)

US_TIER2_CITIES: tuple[tuple[str, str], ...] = (
    # Northeast
    ("Brooklyn", "NY"), ("Queens", "NY"), ("Bronx", "NY"), ("Staten Island", "NY"),
    ("Long Island", "NY"), ("Yonkers", "NY"), ("Rochester", "NY"), ("Syracuse", "NY"),
    ("Albany", "NY"), ("White Plains", "NY"), ("Poughkeepsie", "NY"), ("Binghamton", "NY"),
    ("Utica", "NY"), ("Ithaca", "NY"), ("Saratoga Springs", "NY"),
    ("Paterson", "NJ"), ("Elizabeth", "NJ"), ("Edison", "NJ"), ("Woodbridge", "NJ"),
    ("Toms River", "NJ"), ("Trenton", "NJ"), ("Clifton", "NJ"), ("Camden", "NJ"),
    ("Cherry Hill", "NJ"), ("Paramus", "NJ"), ("Morristown", "NJ"), ("Princeton", "NJ"),
    ("Allentown", "PA"), ("Reading", "PA"), ("Erie", "PA"), ("Scranton", "PA"),
    ("Bethlehem", "PA"), ("Lancaster", "PA"), ("Harrisburg", "PA"), ("York", "PA"),
    ("State College", "PA"), ("King of Prussia", "PA"), ("West Chester", "PA"),
    ("Worcester", "MA"), ("Springfield", "MA"), ("Cambridge", "MA"), ("Lowell", "MA"),
    ("Brockton", "MA"), ("Quincy", "MA"), ("Lynn", "MA"), ("New Bedford", "MA"),
    ("Plymouth", "MA"), ("Framingham", "MA"), ("Cape Cod", "MA"),
    ("Bridgeport", "CT"), ("Stamford", "CT"), ("New Haven", "CT"), ("Waterbury", "CT"),
    ("Norwalk", "CT"), ("Danbury", "CT"), ("Greenwich", "CT"),
    ("Warwick", "RI"), ("Cranston", "RI"), ("Nashua", "NH"), ("Concord", "NH"),
    ("Portsmouth", "NH"), ("Bangor", "ME"), ("Dover", "DE"), ("Newark", "DE"),
    # South Atlantic
    ("Silver Spring", "MD"), ("Rockville", "MD"), ("Frederick", "MD"), ("Annapolis", "MD"),
    ("Columbia", "MD"), ("Towson", "MD"), ("Bethesda", "MD"), ("Gaithersburg", "MD"),
    ("Arlington", "VA"), ("Alexandria", "VA"), ("Newport News", "VA"), ("Hampton", "VA"),
    ("Roanoke", "VA"), ("Lynchburg", "VA"), ("Charlottesville", "VA"), ("Fredericksburg", "VA"),
    ("Ashburn", "VA"), ("Fairfax", "VA"), ("Manassas", "VA"),
    ("Fayetteville", "NC"), ("Cary", "NC"), ("Wilmington", "NC"), ("High Point", "NC"),
    ("Concord", "NC"), ("Asheville", "NC"), ("Greenville", "NC"), ("Gastonia", "NC"),
    ("Greenville", "SC"), ("Myrtle Beach", "SC"), ("Mount Pleasant", "SC"), ("Rock Hill", "SC"),
    ("Spartanburg", "SC"), ("Hilton Head", "SC"),
    ("Augusta", "GA"), ("Columbus", "GA"), ("Macon", "GA"), ("Athens", "GA"),
    ("Sandy Springs", "GA"), ("Roswell", "GA"), ("Alpharetta", "GA"), ("Marietta", "GA"),
    ("Lawrenceville", "GA"),
    ("Hialeah", "FL"), ("Tallahassee", "FL"), ("Port St. Lucie", "FL"), ("Cape Coral", "FL"),
    ("Pembroke Pines", "FL"), ("Hollywood", "FL"), ("Gainesville", "FL"), ("Miramar", "FL"),
    ("Coral Springs", "FL"), ("Clearwater", "FL"), ("Brandon", "FL"), ("Palm Bay", "FL"),
    ("Pompano Beach", "FL"), ("Lakeland", "FL"), ("Boca Raton", "FL"), ("Sarasota", "FL"),
    ("Fort Myers", "FL"), ("Naples", "FL"), ("Daytona Beach", "FL"), ("Melbourne", "FL"),
    ("Ocala", "FL"), ("Pensacola", "FL"), ("Bradenton", "FL"), ("Kissimmee", "FL"),
    ("Delray Beach", "FL"), ("Jupiter", "FL"), ("St. Augustine", "FL"),
    ("Huntington", "WV"), ("Morgantown", "WV"),
    # South Central
    ("Montgomery", "AL"), ("Mobile", "AL"), ("Tuscaloosa", "AL"), ("Hoover", "AL"), ("Dothan", "AL"),
    ("Knoxville", "TN"), ("Chattanooga", "TN"), ("Clarksville", "TN"), ("Murfreesboro", "TN"),
    ("Franklin", "TN"), ("Johnson City", "TN"),
    ("Bowling Green", "KY"), ("Owensboro", "KY"), ("Covington", "KY"),
    ("Gulfport", "MS"), ("Southaven", "MS"), ("Hattiesburg", "MS"), ("Biloxi", "MS"),
    ("Shreveport", "LA"), ("Lafayette", "LA"), ("Lake Charles", "LA"), ("Metairie", "LA"),
    ("Fayetteville", "AR"), ("Fort Smith", "AR"), ("Springdale", "AR"), ("Bentonville", "AR"),
    ("Norman", "OK"), ("Broken Arrow", "OK"), ("Edmond", "OK"), ("Lawton", "OK"),
    ("Frisco", "TX"), ("McKinney", "TX"), ("Amarillo", "TX"), ("Grand Prairie", "TX"),
    ("Brownsville", "TX"), ("Killeen", "TX"), ("Pasadena", "TX"), ("Mesquite", "TX"),
    ("McAllen", "TX"), ("Denton", "TX"), ("Midland", "TX"), ("Waco", "TX"),
    ("Carrollton", "TX"), ("Round Rock", "TX"), ("Abilene", "TX"), ("Pearland", "TX"),
    ("College Station", "TX"), ("Odessa", "TX"), ("Beaumont", "TX"), ("Richardson", "TX"),
    ("The Woodlands", "TX"), ("League City", "TX"), ("Tyler", "TX"), ("Allen", "TX"),
    ("Sugar Land", "TX"), ("Katy", "TX"), ("New Braunfels", "TX"), ("Conroe", "TX"),
    # Midwest
    ("Akron", "OH"), ("Dayton", "OH"), ("Parma", "OH"), ("Canton", "OH"), ("Youngstown", "OH"),
    ("Warren", "MI"), ("Sterling Heights", "MI"), ("Ann Arbor", "MI"), ("Lansing", "MI"),
    ("Flint", "MI"), ("Dearborn", "MI"), ("Troy", "MI"), ("Kalamazoo", "MI"), ("Traverse City", "MI"),
    ("Evansville", "IN"), ("South Bend", "IN"), ("Carmel", "IN"), ("Fishers", "IN"), ("Bloomington", "IN"),
    ("Aurora", "IL"), ("Naperville", "IL"), ("Joliet", "IL"), ("Rockford", "IL"),
    ("Springfield", "IL"), ("Elgin", "IL"), ("Peoria", "IL"), ("Champaign", "IL"),
    ("Schaumburg", "IL"), ("Evanston", "IL"),
    ("Green Bay", "WI"), ("Kenosha", "WI"), ("Racine", "WI"), ("Appleton", "WI"),
    ("Waukesha", "WI"), ("Eau Claire", "WI"), ("Oshkosh", "WI"),
    ("Rochester", "MN"), ("Duluth", "MN"), ("Bloomington", "MN"), ("Brooklyn Park", "MN"),
    ("Plymouth", "MN"), ("St. Cloud", "MN"),
    ("Cedar Rapids", "IA"), ("Davenport", "IA"), ("Sioux City", "IA"), ("Iowa City", "IA"),
    ("Springfield", "MO"), ("Columbia", "MO"), ("Independence", "MO"), ("Lee's Summit", "MO"),
    ("O'Fallon", "MO"), ("St. Charles", "MO"),
    ("Overland Park", "KS"), ("Kansas City", "KS"), ("Olathe", "KS"), ("Topeka", "KS"), ("Lawrence", "KS"),
    ("Bellevue", "NE"), ("Grand Island", "NE"), ("Bismarck", "ND"), ("Rapid City", "SD"),
    # Mountain & West
    ("Fort Collins", "CO"), ("Lakewood", "CO"), ("Thornton", "CO"), ("Arvada", "CO"),
    ("Westminster", "CO"), ("Pueblo", "CO"), ("Boulder", "CO"), ("Centennial", "CO"),
    ("Greeley", "CO"), ("Grand Junction", "CO"),
    ("Peoria", "AZ"), ("Surprise", "AZ"), ("Tempe", "AZ"), ("Yuma", "AZ"), ("Flagstaff", "AZ"), ("Prescott", "AZ"),
    ("West Valley City", "UT"), ("Provo", "UT"), ("West Jordan", "UT"), ("Orem", "UT"),
    ("Sandy", "UT"), ("Ogden", "UT"), ("St. George", "UT"),
    ("Sparks", "NV"), ("Carson City", "NV"), ("Summerlin", "NV"),
    ("Las Cruces", "NM"), ("Rio Rancho", "NM"), ("Santa Fe", "NM"),
    ("Meridian", "ID"), ("Nampa", "ID"), ("Idaho Falls", "ID"), ("Coeur d'Alene", "ID"),
    ("Missoula", "MT"), ("Bozeman", "MT"), ("Great Falls", "MT"), ("Casper", "WY"),
    ("San Bernardino", "CA"), ("Modesto", "CA"), ("Fontana", "CA"), ("Moreno Valley", "CA"),
    ("Glendale", "CA"), ("Huntington Beach", "CA"), ("Santa Clarita", "CA"), ("Garden Grove", "CA"),
    ("Oceanside", "CA"), ("Santa Rosa", "CA"), ("Rancho Cucamonga", "CA"), ("Ontario", "CA"),
    ("Elk Grove", "CA"), ("Corona", "CA"), ("Lancaster", "CA"), ("Palmdale", "CA"),
    ("Salinas", "CA"), ("Pomona", "CA"), ("Hayward", "CA"), ("Escondido", "CA"),
    ("Sunnyvale", "CA"), ("Torrance", "CA"), ("Pasadena", "CA"), ("Orange", "CA"),
    ("Fullerton", "CA"), ("Thousand Oaks", "CA"), ("Roseville", "CA"), ("Concord", "CA"),
    ("Simi Valley", "CA"), ("Santa Clara", "CA"), ("Victorville", "CA"), ("Berkeley", "CA"),
    ("Santa Barbara", "CA"), ("Ventura", "CA"), ("San Mateo", "CA"), ("Carlsbad", "CA"),
    ("Temecula", "CA"), ("Murrieta", "CA"), ("Napa", "CA"), ("San Luis Obispo", "CA"),
    ("Palm Springs", "CA"), ("Walnut Creek", "CA"), ("Palo Alto", "CA"), ("Redding", "CA"),
    ("Vancouver", "WA"), ("Bellevue", "WA"), ("Kent", "WA"), ("Everett", "WA"),
    ("Renton", "WA"), ("Spokane Valley", "WA"), ("Kirkland", "WA"), ("Bellingham", "WA"),
    ("Olympia", "WA"), ("Kennewick", "WA"), ("Yakima", "WA"), ("Redmond", "WA"),
    ("Salem", "OR"), ("Eugene", "OR"), ("Gresham", "OR"), ("Hillsboro", "OR"),
    ("Beaverton", "OR"), ("Bend", "OR"), ("Medford", "OR"), ("Corvallis", "OR"),
    ("Maui", "HI"), ("Fairbanks", "AK"),
)

# ---------------------------------------------------------------------------
# 3. CANADA, AUSTRALIA, IRELAND, NEW ZEALAND, SOUTH AFRICA
# ---------------------------------------------------------------------------

WORLD_CITIES: dict[str, tuple[tuple[str, str, int], ...]] = {
    "CA": (
        ("Toronto", "ON", 1), ("Montreal", "QC", 1), ("Vancouver", "BC", 1), ("Calgary", "AB", 1),
        ("Edmonton", "AB", 1), ("Ottawa", "ON", 1), ("Winnipeg", "MB", 1), ("Quebec City", "QC", 1),
        ("Hamilton", "ON", 1), ("Kitchener", "ON", 1), ("London", "ON", 1), ("Victoria", "BC", 1),
        ("Halifax", "NS", 1), ("Mississauga", "ON", 1), ("Brampton", "ON", 1), ("Surrey", "BC", 1),
        ("Markham", "ON", 1), ("Vaughan", "ON", 1), ("Windsor", "ON", 1), ("Saskatoon", "SK", 1),
        ("Regina", "SK", 1), ("St. John's", "NL", 1),
        ("Oshawa", "ON", 2), ("Richmond Hill", "ON", 2), ("Oakville", "ON", 2), ("Burlington", "ON", 2),
        ("Barrie", "ON", 2), ("Guelph", "ON", 2), ("Cambridge", "ON", 2), ("Waterloo", "ON", 2),
        ("St. Catharines", "ON", 2), ("Niagara Falls", "ON", 2), ("Kingston", "ON", 2), ("Sudbury", "ON", 2),
        ("Thunder Bay", "ON", 2), ("Milton", "ON", 2), ("Ajax", "ON", 2), ("Whitby", "ON", 2),
        ("Peterborough", "ON", 2), ("Brantford", "ON", 2), ("Laval", "QC", 2), ("Gatineau", "QC", 2),
        ("Longueuil", "QC", 2), ("Sherbrooke", "QC", 2), ("Trois-Rivières", "QC", 2),
        ("Burnaby", "BC", 2), ("Richmond", "BC", 2), ("Abbotsford", "BC", 2), ("Coquitlam", "BC", 2),
        ("Kelowna", "BC", 2), ("Langley", "BC", 2), ("Nanaimo", "BC", 2), ("Kamloops", "BC", 2),
        ("Red Deer", "AB", 2), ("Lethbridge", "AB", 2), ("Moncton", "NB", 2), ("Saint John", "NB", 2),
        ("Fredericton", "NB", 2), ("Charlottetown", "PE", 2),
    ),
    "AU": (
        ("Sydney", "NSW", 1), ("Melbourne", "VIC", 1), ("Brisbane", "QLD", 1), ("Perth", "WA", 1),
        ("Adelaide", "SA", 1), ("Gold Coast", "QLD", 1), ("Canberra", "ACT", 1), ("Newcastle", "NSW", 1),
        ("Sunshine Coast", "QLD", 1), ("Wollongong", "NSW", 1), ("Geelong", "VIC", 1), ("Hobart", "TAS", 1),
        ("Townsville", "QLD", 1), ("Cairns", "QLD", 1), ("Darwin", "NT", 1), ("Toowoomba", "QLD", 1),
        ("Parramatta", "NSW", 2), ("Penrith", "NSW", 2), ("Blacktown", "NSW", 2), ("Liverpool", "NSW", 2),
        ("Campbelltown", "NSW", 2), ("Central Coast", "NSW", 2), ("Northern Beaches", "NSW", 2),
        ("Sutherland", "NSW", 2), ("Albury", "NSW", 2), ("Wagga Wagga", "NSW", 2), ("Coffs Harbour", "NSW", 2),
        ("Port Macquarie", "NSW", 2), ("Tamworth", "NSW", 2), ("Orange", "NSW", 2), ("Dubbo", "NSW", 2),
        ("Dandenong", "VIC", 2), ("Frankston", "VIC", 2), ("Ringwood", "VIC", 2), ("Epping", "VIC", 2),
        ("Werribee", "VIC", 2), ("Ballarat", "VIC", 2), ("Bendigo", "VIC", 2), ("Shepparton", "VIC", 2),
        ("Mornington Peninsula", "VIC", 2), ("Ipswich", "QLD", 2), ("Logan", "QLD", 2), ("Mackay", "QLD", 2),
        ("Rockhampton", "QLD", 2), ("Bundaberg", "QLD", 2), ("Hervey Bay", "QLD", 2),
        ("Fremantle", "WA", 2), ("Joondalup", "WA", 2), ("Mandurah", "WA", 2), ("Bunbury", "WA", 2),
        ("Launceston", "TAS", 2), ("Mount Gambier", "SA", 2),
    ),
    "IE": (
        ("Dublin", "Leinster", 1), ("Cork", "Munster", 1), ("Limerick", "Munster", 1),
        ("Galway", "Connacht", 1), ("Waterford", "Munster", 1), ("Drogheda", "Louth", 1),
        ("Dundalk", "Louth", 1), ("Swords", "Dublin", 1), ("Bray", "Wicklow", 1), ("Navan", "Meath", 1),
        ("Kilkenny", "Leinster", 1), ("Ennis", "Clare", 1), ("Carlow", "Leinster", 1), ("Tralee", "Kerry", 1),
        ("Newbridge", "Kildare", 2), ("Naas", "Kildare", 2), ("Athlone", "Westmeath", 2),
        ("Portlaoise", "Laois", 2), ("Mullingar", "Westmeath", 2), ("Wexford", "Leinster", 2),
        ("Letterkenny", "Donegal", 2), ("Sligo", "Connacht", 2), ("Clonmel", "Tipperary", 2),
        ("Castlebar", "Mayo", 2), ("Cavan", "Ulster", 2), ("Monaghan", "Ulster", 2),
        ("Tullamore", "Offaly", 2), ("Arklow", "Wicklow", 2), ("Longford", "Leinster", 2),
        ("Roscommon", "Connacht", 2), ("Killarney", "Kerry", 2),
    ),
    "NZ": (
        ("Auckland", "Auckland", 1), ("Wellington", "Wellington", 1), ("Christchurch", "Canterbury", 1),
        ("Hamilton", "Waikato", 1), ("Tauranga", "Bay of Plenty", 1), ("Dunedin", "Otago", 1),
        ("Lower Hutt", "Wellington", 1), ("Palmerston North", "Manawatu", 1), ("Napier", "Hawkes Bay", 1),
        ("North Shore", "Auckland", 2), ("Manukau", "Auckland", 2), ("Waitakere", "Auckland", 2),
        ("Rotorua", "Bay of Plenty", 2), ("New Plymouth", "Taranaki", 2), ("Whangarei", "Northland", 2),
        ("Nelson", "Nelson", 2), ("Invercargill", "Southland", 2), ("Hastings", "Hawkes Bay", 2),
        ("Queenstown", "Otago", 2), ("Gisborne", "Gisborne", 2), ("Timaru", "Canterbury", 2),
        ("Blenheim", "Marlborough", 2), ("Taupo", "Waikato", 2),
    ),
    "ZA": (
        ("Johannesburg", "Gauteng", 1), ("Cape Town", "Western Cape", 1), ("Durban", "KwaZulu-Natal", 1),
        ("Pretoria", "Gauteng", 1), ("Port Elizabeth", "Eastern Cape", 1), ("Bloemfontein", "Free State", 1),
        ("Sandton", "Gauteng", 1), ("Centurion", "Gauteng", 1), ("Midrand", "Gauteng", 1),
        ("East London", "Eastern Cape", 2), ("Pietermaritzburg", "KwaZulu-Natal", 2),
        ("Polokwane", "Limpopo", 2), ("Nelspruit", "Mpumalanga", 2), ("George", "Western Cape", 2),
        ("Stellenbosch", "Western Cape", 2), ("Somerset West", "Western Cape", 2),
        ("Boksburg", "Gauteng", 2), ("Benoni", "Gauteng", 2), ("Roodepoort", "Gauteng", 2),
        ("Randburg", "Gauteng", 2), ("Umhlanga", "KwaZulu-Natal", 2),
    ),
    # Major European Window Markets
    "DE": (
        ("Berlin", "", 1), ("Hamburg", "", 1), ("München", "", 1), ("Köln", "", 1),
        ("Frankfurt am Main", "", 1), ("Stuttgart", "", 1), ("Düsseldorf", "", 1), ("Leipzig", "", 1),
        ("Dortmund", "", 1), ("Essen", "", 1), ("Bremen", "", 1), ("Dresden", "", 1),
        ("Hannover", "", 1), ("Nürnberg", "", 1), ("Duisburg", "", 1), ("Bochum", "", 1),
        ("Wuppertal", "", 2), ("Bielefeld", "", 2), ("Bonn", "", 2), ("Münster", "", 2),
        ("Mannheim", "", 2), ("Karlsruhe", "", 2), ("Augsburg", "", 2), ("Wiesbaden", "", 2),
        ("Mönchengladbach", "", 2), ("Gelsenkirchen", "", 2), ("Aachen", "", 2), ("Braunschweig", "", 2),
        ("Kiel", "", 2), ("Chemnitz", "", 2), ("Halle", "", 2), ("Magdeburg", "", 2),
        ("Freiburg", "", 2), ("Krefeld", "", 2), ("Mainz", "", 2), ("Lübeck", "", 2),
        ("Erfurt", "", 2), ("Oberhausen", "", 2), ("Rostock", "", 2), ("Kassel", "", 2),
        ("Hagen", "", 2), ("Potsdam", "", 2), ("Saarbrücken", "", 2), ("Regensburg", "", 2),
        ("Ingolstadt", "", 2), ("Würzburg", "", 2), ("Ulm", "", 2), ("Heilbronn", "", 2),
        ("Osnabrück", "", 2), ("Oldenburg", "", 2), ("Darmstadt", "", 2), ("Heidelberg", "", 2),
    ),
    "FR": (
        ("Paris", "", 1), ("Marseille", "", 1), ("Lyon", "", 1), ("Toulouse", "", 1),
        ("Nice", "", 1), ("Nantes", "", 1), ("Montpellier", "", 1), ("Strasbourg", "", 1),
        ("Bordeaux", "", 1), ("Lille", "", 1), ("Rennes", "", 1), ("Reims", "", 1),
        ("Toulon", "", 1), ("Saint-Étienne", "", 1), ("Grenoble", "", 1),
        ("Le Havre", "", 2), ("Dijon", "", 2), ("Angers", "", 2), ("Nîmes", "", 2),
        ("Villeurbanne", "", 2), ("Clermont-Ferrand", "", 2), ("Le Mans", "", 2),
        ("Aix-en-Provence", "", 2), ("Brest", "", 2), ("Tours", "", 2), ("Amiens", "", 2),
        ("Limoges", "", 2), ("Annecy", "", 2), ("Perpignan", "", 2), ("Metz", "", 2),
        ("Besançon", "", 2), ("Orléans", "", 2), ("Rouen", "", 2), ("Mulhouse", "", 2),
        ("Caen", "", 2), ("Nancy", "", 2), ("Avignon", "", 2), ("Poitiers", "", 2),
        ("Pau", "", 2), ("La Rochelle", "", 2), ("Cannes", "", 2), ("Valence", "", 2),
    ),
    "NL": (
        ("Amsterdam", "", 1), ("Rotterdam", "", 1), ("Den Haag", "", 1), ("Utrecht", "", 1),
        ("Eindhoven", "", 1), ("Groningen", "", 1), ("Tilburg", "", 1), ("Almere", "", 1),
        ("Breda", "", 1), ("Nijmegen", "", 1), ("Apeldoorn", "", 1), ("Haarlem", "", 1),
        ("Arnhem", "", 2), ("Enschede", "", 2), ("Amersfoort", "", 2), ("Zaanstad", "", 2),
        ("Den Bosch", "", 2), ("Zwolle", "", 2), ("Leiden", "", 2), ("Maastricht", "", 2),
        ("Dordrecht", "", 2), ("Alphen aan den Rijn", "", 2), ("Alkmaar", "", 2), ("Delft", "", 2),
        ("Leeuwarden", "", 2), ("Venlo", "", 2), ("Deventer", "", 2), ("Hilversum", "", 2),
    ),
    "BE": (
        ("Bruxelles", "", 1), ("Antwerpen", "", 1), ("Gent", "", 1), ("Charleroi", "", 1),
        ("Liège", "", 1), ("Brugge", "", 1), ("Namur", "", 1), ("Leuven", "", 1),
        ("Mons", "", 2), ("Mechelen", "", 2), ("Aalst", "", 2), ("Hasselt", "", 2),
        ("Kortrijk", "", 2), ("Oostende", "", 2), ("Genk", "", 2), ("Roeselare", "", 2),
    ),
    "AT": (
        ("Wien", "", 1), ("Graz", "", 1), ("Linz", "", 1), ("Salzburg", "", 1),
        ("Innsbruck", "", 1), ("Klagenfurt", "", 1),
        ("Villach", "", 2), ("Wels", "", 2), ("Sankt Pölten", "", 2), ("Dornbirn", "", 2),
    ),
    "CH": (
        ("Zürich", "", 1), ("Genève", "", 1), ("Basel", "", 1), ("Lausanne", "", 1),
        ("Bern", "", 1), ("Winterthur", "", 1), ("Luzern", "", 1), ("St. Gallen", "", 1),
        ("Lugano", "", 2), ("Biel", "", 2), ("Thun", "", 2), ("Fribourg", "", 2), ("Aarau", "", 2),
    ),
    "ES": (
        ("Madrid", "", 1), ("Barcelona", "", 1), ("Valencia", "", 1), ("Sevilla", "", 1),
        ("Zaragoza", "", 1), ("Málaga", "", 1), ("Murcia", "", 1), ("Palma de Mallorca", "", 1),
        ("Bilbao", "", 1), ("Alicante", "", 1), ("Córdoba", "", 1), ("Valladolid", "", 1),
        ("Vigo", "", 2), ("Gijón", "", 2), ("Granada", "", 2), ("A Coruña", "", 2),
        ("Vitoria-Gasteiz", "", 2), ("Elche", "", 2), ("Oviedo", "", 2), ("Pamplona", "", 2),
        ("Santander", "", 2), ("San Sebastián", "", 2), ("Marbella", "", 2), ("Tarragona", "", 2),
        ("Girona", "", 2), ("Salamanca", "", 2), ("Burgos", "", 2), ("Las Palmas", "", 2),
        ("Tenerife", "", 2),
    ),
    "IT": (
        ("Roma", "", 1), ("Milano", "", 1), ("Napoli", "", 1), ("Torino", "", 1),
        ("Palermo", "", 1), ("Genova", "", 1), ("Bologna", "", 1), ("Firenze", "", 1),
        ("Bari", "", 1), ("Catania", "", 1), ("Verona", "", 1), ("Venezia", "", 1),
        ("Padova", "", 1), ("Brescia", "", 1), ("Bergamo", "", 1),
        ("Trieste", "", 2), ("Parma", "", 2), ("Modena", "", 2), ("Reggio Emilia", "", 2),
        ("Perugia", "", 2), ("Ravenna", "", 2), ("Vicenza", "", 2), ("Treviso", "", 2),
        ("Monza", "", 2), ("Como", "", 2), ("Varese", "", 2), ("Udine", "", 2),
        ("Cagliari", "", 2), ("Pescara", "", 2), ("Rimini", "", 2), ("Salerno", "", 2),
        ("Bolzano", "", 2), ("Trento", "", 2), ("Pisa", "", 2), ("Ancona", "", 2),
    ),
    "PT": (
        ("Lisboa", "", 1), ("Porto", "", 1), ("Braga", "", 1), ("Coimbra", "", 1),
        ("Faro", "", 1), ("Aveiro", "", 1), ("Setúbal", "", 1),
        ("Leiria", "", 2), ("Guimarães", "", 2), ("Viseu", "", 2), ("Viana do Castelo", "", 2),
        ("Sintra", "", 2), ("Cascais", "", 2), ("Funchal", "", 2),
    ),
    "PL": (
        # Poland is Europe's #1 window exporter — massive density of manufacturers!
        ("Warszawa", "", 1), ("Kraków", "", 1), ("Wrocław", "", 1), ("Łódź", "", 1),
        ("Poznań", "", 1), ("Gdańsk", "", 1), ("Szczecin", "", 1), ("Bydgoszcz", "", 1),
        ("Lublin", "", 1), ("Białystok", "", 1), ("Katowice", "", 1), ("Gdynia", "", 1),
        ("Częstochowa", "", 2), ("Radom", "", 2), ("Rzeszów", "", 2), ("Toruń", "", 2),
        ("Kielce", "", 2), ("Gliwice", "", 2), ("Olsztyn", "", 2), ("Bielsko-Biała", "", 2),
        ("Opole", "", 2), ("Zielona Góra", "", 2), ("Nowy Sącz", "", 2), ("Tarnów", "", 2),
        ("Kalisz", "", 2), ("Koszalin", "", 2), ("Słupsk", "", 2),
    ),
    "SE": (
        ("Stockholm", "", 1), ("Göteborg", "", 1), ("Malmö", "", 1), ("Uppsala", "", 1),
        ("Västerås", "", 2), ("Örebro", "", 2), ("Linköping", "", 2), ("Helsingborg", "", 2),
        ("Jönköping", "", 2), ("Norrköping", "", 2), ("Umeå", "", 2),
    ),
    "NO": (
        ("Oslo", "", 1), ("Bergen", "", 1), ("Trondheim", "", 1), ("Stavanger", "", 1),
        ("Kristiansand", "", 2), ("Drammen", "", 2), ("Fredrikstad", "", 2), ("Tromsø", "", 2),
    ),
    "DK": (
        ("København", "", 1), ("Aarhus", "", 1), ("Odense", "", 1), ("Aalborg", "", 1),
        ("Esbjerg", "", 2), ("Randers", "", 2), ("Kolding", "", 2), ("Vejle", "", 2), ("Roskilde", "", 2),
    ),
    "FI": (
        ("Helsinki", "", 1), ("Espoo", "", 1), ("Tampere", "", 1), ("Turku", "", 1), ("Oulu", "", 1),
        ("Jyväskylä", "", 2), ("Lahti", "", 2), ("Kuopio", "", 2),
    ),
    "CZ": (
        ("Praha", "", 1), ("Brno", "", 1), ("Ostrava", "", 1), ("Plzeň", "", 1),
        ("Liberec", "", 2), ("Olomouc", "", 2), ("České Budějovice", "", 2), ("Hradec Králové", "", 2), ("Zlín", "", 2),
    ),
    "RO": (
        ("București", "", 1), ("Cluj-Napoca", "", 1), ("Timișoara", "", 1), ("Iași", "", 1),
        ("Constanța", "", 1), ("Brașov", "", 1), ("Craiova", "", 2), ("Oradea", "", 2), ("Sibiu", "", 2),
    ),
    "HU": (
        ("Budapest", "", 1), ("Debrecen", "", 1), ("Szeged", "", 1), ("Miskolc", "", 1),
        ("Pécs", "", 2), ("Győr", "", 2), ("Székesfehérvár", "", 2),
    ),
    "GR": (
        ("Αθήνα", "", 1), ("Θεσσαλονίκη", "", 1), ("Πάτρα", "", 1), ("Ηράκλειο", "", 1),
        ("Λάρισα", "", 2), ("Βόλος", "", 2),
    ),
    "AE": (
        ("Dubai", "Dubai", 1), ("Abu Dhabi", "Abu Dhabi", 1), ("Sharjah", "Sharjah", 1), ("Ajman", "Ajman", 2),
    ),
    "SG": (("Singapore", "Singapore", 1),),
    "IN": (
        ("Mumbai", "MH", 1), ("Delhi", "DL", 1), ("Bengaluru", "KA", 1), ("Hyderabad", "TS", 1),
        ("Chennai", "TN", 1), ("Pune", "MH", 1), ("Ahmedabad", "GJ", 1), ("Kolkata", "WB", 1),
        ("Gurgaon", "HR", 2), ("Noida", "UP", 2), ("Surat", "GJ", 2), ("Jaipur", "RJ", 2),
        ("Chandigarh", "CH", 2), ("Coimbatore", "TN", 2), ("Kochi", "KL", 2),
    ),
    "MX": (
        ("Ciudad de México", "", 1), ("Guadalajara", "", 1), ("Monterrey", "", 1), ("Puebla", "", 1),
        ("Tijuana", "", 1), ("Querétaro", "", 1), ("León", "", 2), ("Mérida", "", 2), ("Cancún", "", 2),
    ),
    "BR": (
        ("São Paulo", "SP", 1), ("Rio de Janeiro", "RJ", 1), ("Belo Horizonte", "MG", 1),
        ("Curitiba", "PR", 1), ("Porto Alegre", "RS", 1), ("Brasília", "DF", 1),
        ("Campinas", "SP", 2), ("Florianópolis", "SC", 2), ("Joinville", "SC", 2), ("Goiânia", "GO", 2),
    ),
}

# Ordered list of 50+ ISO-3166-1 alpha-2 countries for OpenStreetMap Overpass sweeps
OSM_COUNTRIES_PRIORITY: tuple[str, ...] = (
    # Core English-speaking markets
    "GB", "US", "CA", "AU", "IE", "NZ", "ZA",
    # High-density OSM European window/glazing markets
    "DE", "FR", "NL", "AT", "CH", "BE", "IT", "ES", "PL", "CZ", "SE", "DK", "NO", "FI",
    "PT", "HU", "SK", "SI", "HR", "RO", "BG", "GR", "EE", "LV", "LT", "LU", "IS", "CY", "MT",
    # Major global markets
    "JP", "KR", "SG", "AE", "IL", "TR", "IN", "BR", "MX", "AR", "CL", "CO", "UA", "RS",
)

# Country geographic bounding boxes for Google Places Adaptive Quadtree sweeps
# Format: (south, west, north, east, initial_grid_rows, initial_grid_cols)
COUNTRY_BOUNDING_BOXES: dict[str, tuple[float, float, float, float, int, int]] = {
    "GB": (49.90, -8.20, 58.70, 1.80, 10, 8),
    "IE": (51.40, -10.50, 55.40, -5.90, 5, 5),
    "US": (24.50, -124.80, 49.40, -66.90, 12, 18),
    "CA": (42.00, -131.00, 56.00, -52.50, 6, 14),
    "AU": (-43.60, 113.00, -10.50, 153.70, 8, 10),
    "NZ": (-47.00, 166.40, -34.40, 178.60, 6, 5),
    "DE": (47.27, 5.86, 55.06, 15.04, 8, 8),
    "FR": (42.30, -4.80, 51.10, 8.25, 8, 8),
    "NL": (50.75, 3.35, 53.55, 7.23, 5, 5),
    "BE": (49.50, 2.54, 51.51, 6.41, 4, 4),
    "ES": (36.00, -9.30, 43.80, 3.35, 7, 8),
    "IT": (36.65, 6.62, 47.10, 18.52, 8, 7),
    "PL": (49.00, 14.12, 54.84, 24.15, 6, 7),
    "AT": (46.37, 9.53, 49.02, 17.16, 4, 6),
    "CH": (45.82, 5.95, 47.81, 10.49, 4, 5),
}

# Mapping ISO country code -> `ddgs` region tag (must be `country-lang`)
COUNTRY_TO_DDGS_REGION: dict[str, str] = {
    "GB": "uk-en",
    "US": "us-en",
    "CA": "ca-en",
    "AU": "au-en",
    "IE": "ie-en",
    "NZ": "nz-en",
    "ZA": "za-en",
    "SG": "sg-en",
    "IN": "in-en",
    "AE": "xa-en",
    "DE": "de-de",
    "AT": "at-de",
    "CH": "ch-de",
    "FR": "fr-fr",
    "BE": "be-nl",
    "NL": "nl-nl",
    "ES": "es-es",
    "MX": "mx-es",
    "AR": "ar-es",
    "CL": "cl-es",
    "IT": "it-it",
    "PT": "pt-pt",
    "BR": "br-pt",
    "PL": "pl-pl",
    "CZ": "cz-cs",
    "SE": "se-sv",
    "NO": "no-no",
    "DK": "dk-da",
    "FI": "fi-fi",
    "RO": "ro-ro",
    "HU": "hu-hu",
    "GR": "gr-el",
}

# Mapping ISO country code -> Google `hl` language code
COUNTRY_TO_LANG: dict[str, str] = {
    "GB": "en", "US": "en", "CA": "en", "AU": "en", "IE": "en", "NZ": "en",
    "ZA": "en", "SG": "en", "IN": "en", "AE": "en",
    "DE": "de", "AT": "de", "CH": "de",
    "FR": "fr", "BE": "fr", "NL": "nl",
    "ES": "es", "MX": "es", "AR": "es", "CL": "es",
    "IT": "it", "PT": "pt", "BR": "pt",
    "PL": "pl", "CZ": "cs", "SE": "sv", "NO": "no", "DK": "da", "FI": "fi",
    "RO": "ro", "HU": "hu", "GR": "el",
}


def get_locations(
    countries: list[str] | None = None,
    *,
    max_tier: int = 2,
    include_uk_postcodes: bool = False,
    include_uk_postcode_districts: bool = False,
    custom_file: str | Path | None = None,
) -> list[GeoLocation]:
    """Return a structured, deduplicated list of geographic search targets.

    - `max_tier=1`: Major metros + London boroughs (~350 global locations)
    - `max_tier=2`: All mid-size cities & towns (~1,200+ global locations)
    - `max_tier=3` or `include_uk_postcodes=True`: Adds all 121 UK Royal Mail postcode areas
    - `include_uk_postcode_districts=True`: Expands UK postcode areas to ~2,400 districts (AL1..AL10, B1..B45, etc.)
    - `custom_file`: Optional `.txt` (one location per line) or `.csv` (`name,country,region`) to harvest any list of 40,000 ZIPs/postcodes!
    """
    if custom_file:
        return load_custom_locations(custom_file, default_country=(countries[0] if countries else "GB"))

    target_ccs = [c.upper() for c in countries] if countries else ["GB", "US", "CA", "AU", "IE", "NZ"]
    locations: list[GeoLocation] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(loc: GeoLocation) -> None:
        key = (loc.country, loc.name.lower(), loc.region.lower())
        if key not in seen:
            seen.add(key)
            locations.append(loc)

    for cc in target_ccs:
        if cc == "GB":
            for city, region in UK_TIER1_CITIES:
                _add(GeoLocation(name=city, country="GB", region=region, tier=1))
            if max_tier >= 2:
                for town, region in UK_TIER2_TOWNS:
                    _add(GeoLocation(name=town, country="GB", region=region, tier=2))
            if max_tier >= 3 or include_uk_postcodes:
                for area in UK_POSTCODE_AREAS:
                    _add(GeoLocation(name=area, country="GB", region="UK Postcode", tier=3))
            if include_uk_postcode_districts:
                for area in UK_POSTCODE_AREAS:
                    max_num = 30 if area in ("B", "M", "G", "S", "L", "LS", "NG", "NE", "SE", "SW", "E", "N", "NW", "W") else 16
                    for num in range(1, max_num + 1):
                        _add(GeoLocation(name=f"{area}{num}", country="GB", region=area, tier=3))
        elif cc == "US":
            for city, state in US_TIER1_CITIES:
                _add(GeoLocation(name=city, country="US", region=state, tier=1))
            if max_tier >= 2:
                for city, state in US_TIER2_CITIES:
                    _add(GeoLocation(name=city, country="US", region=state, tier=2))
        elif cc in WORLD_CITIES:
            for city, region, tier in WORLD_CITIES[cc]:
                if tier <= max_tier:
                    _add(GeoLocation(name=city, country=cc, region=region, tier=tier))
        else:
            # Fallback country-level search for any other ISO-2 country
            _add(GeoLocation(name=cc, country=cc, region="", tier=1))

    return locations


def load_custom_locations(path: str | Path, default_country: str = "GB") -> list[GeoLocation]:
    """Load arbitrary cities, ZIP codes, or postcodes from a `.txt` or `.csv` file."""
    p = Path(path)
    out: list[GeoLocation] = []
    seen: set[tuple[str, str, str]] = set()

    text = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() == ".csv":
        reader = csv.DictReader(text.splitlines())
        for row in reader:
            norm_row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            name = (
                norm_row.get("name")
                or norm_row.get("city")
                or norm_row.get("town")
                or norm_row.get("postcode")
                or norm_row.get("zip")
                or norm_row.get("location")
                or ""
            )
            if not name:
                continue
            country = (norm_row.get("country") or default_country).upper()[:2]
            region = norm_row.get("region") or norm_row.get("state") or norm_row.get("county") or ""
            lat = float(norm_row["lat"]) if norm_row.get("lat") else None
            lon = float(norm_row["lon"]) if norm_row.get("lon") else None
            key = (country, name.lower(), region.lower())
            if key not in seen:
                seen.add(key)
                out.append(GeoLocation(name=name, country=country, region=region, lat=lat, lon=lon, tier=1))
    else:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 3:
                name, region, country = parts[0], parts[1], parts[2].upper()[:2]
            elif len(parts) == 2 and len(parts[1]) == 2 and default_country == "US":
                name, region, country = parts[0], parts[1].upper(), "US"
            elif len(parts) == 2 and len(parts[1]) == 2:
                name, region, country = parts[0], "", parts[1].upper()
            else:
                name, region, country = line, "", default_country.upper()
            key = (country, name.lower(), region.lower())
            if key not in seen:
                seen.add(key)
                out.append(GeoLocation(name=name, country=country, region=region, tier=1))
    return out


def generate_country_grid(country: str, rows: int | None = None, cols: int | None = None) -> list[BoundingBox]:
    """Tile a country's bounding box into initial cells for Adaptive Quadtree Google Maps sweeps."""
    cc = country.upper()
    spec = COUNTRY_BOUNDING_BOXES.get(cc)
    if not spec:
        return []
    south, west, north, east, default_rows, default_cols = spec
    r_count = rows or default_rows
    c_count = cols or default_cols
    d_lat = (north - south) / r_count
    d_lon = (east - west) / c_count

    boxes: list[BoundingBox] = []
    for r in range(r_count):
        for c in range(c_count):
            s = round(south + r * d_lat, 6)
            n = round(south + (r + 1) * d_lat, 6)
            w = round(west + c * d_lon, 6)
            e = round(west + (c + 1) * d_lon, 6)
            boxes.append(
                BoundingBox(
                    south=s,
                    west=w,
                    north=n,
                    east=e,
                    country=cc,
                    label=f"{cc}-r{r}c{c}",
                    depth=0,
                )
            )
    return boxes
