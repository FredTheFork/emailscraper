"""Core data structures shared across harvesters, database, verifier, and exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class VerifyStatus(IntEnum):
    """HTTP + live-content verification status for a discovered domain."""

    UNVERIFIED = 0
    LIVE_RELEVANT = 1
    DEAD_OR_ERROR = -1
    PARKED = -2
    IRRELEVANT = -3


# Canonical window & glazing industry sub-categories
WINDOW_CATEGORIES: dict[str, str] = {
    "double_triple_glazing": "Double, Triple & Secondary Glazing",
    "upvc_vinyl": "uPVC, PVCu & Vinyl Windows",
    "timber_wood": "Timber, Sash, Casement & Wooden Windows",
    "aluminium": "Aluminium, Bi-Fold, Sliding & Slimline Windows",
    "steel_crittall": "Steel, Crittall & Heritage Metal Windows",
    "glass_glaziers": "Glaziers, Flat Glass, Sealed Units & Glass Merchants",
    "skylights_conservatories": "Skylights, Roof Lanterns, Conservatories & Sunrooms",
    "commercial_curtain_wall": "Commercial Glazing, Curtain Walling, Facades & Shopfronts",
    "manufacturers_suppliers": "Window Manufacturers, Fabricators, Trade Suppliers & Hardware",
    "installers_replacement": "Window Installers, Replacement, Repair & Restoration",
    "stained_decorative_glass": "Stained, Leaded, Etched & Architectural Decorative Glass",
    "window_film_tinting": "Architectural Window Film, Solar & Security Glazing Film",
    "window_treatments": "Window Shutters, Blinds & Louvres",
    "window_cleaning": "Window Cleaning & Exterior Glass Washing",
    "auto_glass": "Automotive Windscreens & Vehicle Glass",
    "general_windows": "General Window & Door Businesses",
}


@dataclass(slots=True)
class FilterOptions:
    """User-configurable switches controlling edge sub-verticals and strictness."""

    min_confidence: float = 0.55
    include_treatments: bool = False       # Blinds/shutters-only shops (window+shutter combos always pass)
    include_tinting: bool = True           # Architectural window film/solar film (car tint still rejected)
    include_stained_glass: bool = True     # Stained & leaded glass window studios
    include_conservatories: bool = True    # Conservatories, orangeries, sunrooms, roof lanterns
    include_window_cleaning: bool = False  # Pure window cleaners (off by default; toggle on if desired)
    include_auto_glass: bool = False       # Windshields / car glass (off by default; toggle on if desired)
    allowed_countries: set[str] | None = None  # Optional ISO-2 filter (only filters when country is known)


@dataclass(slots=True)
class ClassificationResult:
    """Output of the window/glazing relevance classifier."""

    accepted: bool
    confidence: float
    categories: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(slots=True)
class CandidateRecord:
    """A raw or classified business website record ready for DB upsert."""

    url: str
    domain: str
    source: str
    confidence: float = 0.70
    categories: list[str] = field(default_factory=list)
    business_name: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    postcode: str | None = None
    address: str | None = None
    phone: str | None = None
    lat: float | None = None
    lon: float | None = None
    sample_query: str | None = None
    page_title: str | None = None
    meta_description: str | None = None


@dataclass(slots=True)
class SourceRunResult:
    """Summary metrics produced by running a single harvester source."""

    source: str
    tasks_completed: int = 0
    tasks_skipped_checkpoint: int = 0
    candidates_seen: int = 0
    new_domains_added: int = 0
    existing_domains_merged: int = 0
    rejected_count: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    notes: str = ""


@dataclass(slots=True)
class GeoLocation:
    """A city, town, postcode area, or region in the search grid."""

    name: str
    country: str          # ISO-3166-1 alpha-2, e.g. "GB", "US"
    region: str = ""      # State, county, province
    lat: float | None = None
    lon: float | None = None
    tier: int = 1         # 1 = major/core, 2 = medium, 3 = granular (postcodes/smaller towns)

    @property
    def search_label(self) -> str:
        """Human query label used in search engines, e.g. 'Watford UK' or 'Austin TX'."""
        if self.country == "US" and self.region:
            return f"{self.name}, {self.region}"
        if self.country == "CA" and self.region:
            return f"{self.name}, {self.region}"
        if self.country == "AU" and self.region:
            return f"{self.name} {self.region}"
        if self.country == "GB":
            return f"{self.name} UK"
        country_names = {
            "IE": "Ireland",
            "NZ": "New Zealand",
            "ZA": "South Africa",
            "DE": "Deutschland",
            "AT": "Österreich",
            "CH": "Schweiz",
            "FR": "France",
            "BE": "Belgique",
            "NL": "Nederland",
            "ES": "España",
            "IT": "Italia",
            "PT": "Portugal",
            "PL": "Polska",
            "SE": "Sverige",
            "NO": "Norge",
            "DK": "Danmark",
            "FI": "Suomi",
            "CZ": "Česko",
            "RO": "România",
            "HU": "Magyarország",
            "GR": "Greece",
            "IN": "India",
            "SG": "Singapore",
            "AE": "UAE",
            "MX": "México",
            "BR": "Brasil",
        }
        suffix = country_names.get(self.country, self.country)
        return f"{self.name} {suffix}"


@dataclass(slots=True)
class BoundingBox:
    """Geographic rectangle for adaptive quadtree Google Maps sweeps."""

    south: float
    west: float
    north: float
    east: float
    country: str
    label: str = ""
    depth: int = 0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.south + self.north) / 2.0, (self.west + self.east) / 2.0)

    @property
    def approx_width_km(self) -> float:
        import math

        mid_lat = math.radians((self.south + self.north) / 2.0)
        lat_km = abs(self.north - self.south) * 111.32
        lon_km = abs(self.east - self.west) * 111.32 * max(0.1, math.cos(mid_lat))
        return max(lat_km, lon_km)

    def subdivide(self) -> list[BoundingBox]:
        """Split this rectangle into 4 equal NW/NE/SW/SE quadrants."""
        mid_lat = round((self.south + self.north) / 2.0, 6)
        mid_lon = round((self.west + self.east) / 2.0, 6)
        next_depth = self.depth + 1
        return [
            BoundingBox(mid_lat, self.west, self.north, mid_lon, self.country, f"{self.label}:NW", next_depth),
            BoundingBox(mid_lat, mid_lon, self.north, self.east, self.country, f"{self.label}:NE", next_depth),
            BoundingBox(self.south, self.west, mid_lat, mid_lon, self.country, f"{self.label}:SW", next_depth),
            BoundingBox(self.south, mid_lon, mid_lat, self.east, self.country, f"{self.label}:SE", next_depth),
        ]

    @property
    def key(self) -> str:
        return f"{self.country}:{self.south:.5f},{self.west:.5f},{self.north:.5f},{self.east:.5f}"
