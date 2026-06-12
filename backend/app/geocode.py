"""Turn place names into coordinates.

Primary path is a built-in gazetteer of common North-American road-trip
anchors (plus a few world cities). It's offline, deterministic, and free — which
keeps the heuristic planner fast and makes tests reproducible.

An optional live fallback hits OpenStreetMap's Nominatim, but only when
``ROADTRIP_USE_NOMINATIM=1`` is set, so we never make surprise network calls in
tests or first-launch. Failures there degrade gracefully to ``None`` and the
planner's own fallbacks take over.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from functools import lru_cache

from .schemas import Coordinate


@dataclass(frozen=True)
class GeocodeResult:
    name: str
    coord: Coordinate


# (normalized key, display name, lat, lng)
_GAZETTEER: tuple[tuple[str, str, float, float], ...] = (
    # --- US / Canada cities ---
    ("san francisco", "San Francisco, CA", 37.7749, -122.4194),
    ("los angeles", "Los Angeles, CA", 34.0522, -118.2437),
    ("san diego", "San Diego, CA", 32.7157, -117.1611),
    ("san jose", "San Jose, CA", 37.3382, -121.8863),
    ("sacramento", "Sacramento, CA", 38.5816, -121.4944),
    ("las vegas", "Las Vegas, NV", 36.1699, -115.1398),
    ("reno", "Reno, NV", 39.5296, -119.8138),
    ("seattle", "Seattle, WA", 47.6062, -122.3321),
    ("portland", "Portland, OR", 45.5152, -122.6784),
    ("boise", "Boise, ID", 43.6150, -116.2023),
    ("denver", "Denver, CO", 39.7392, -104.9903),
    ("phoenix", "Phoenix, AZ", 33.4484, -112.0740),
    ("flagstaff", "Flagstaff, AZ", 35.1983, -111.6513),
    ("salt lake city", "Salt Lake City, UT", 40.7608, -111.8910),
    ("albuquerque", "Albuquerque, NM", 35.0844, -106.6504),
    ("santa fe", "Santa Fe, NM", 35.6870, -105.9378),
    ("chicago", "Chicago, IL", 41.8781, -87.6298),
    ("minneapolis", "Minneapolis, MN", 44.9778, -93.2650),
    ("kansas city", "Kansas City, MO", 39.0997, -94.5786),
    ("saint louis", "St. Louis, MO", 38.6270, -90.1994),
    ("st louis", "St. Louis, MO", 38.6270, -90.1994),
    ("dallas", "Dallas, TX", 32.7767, -96.7970),
    ("houston", "Houston, TX", 29.7604, -95.3698),
    ("austin", "Austin, TX", 30.2672, -97.7431),
    ("new orleans", "New Orleans, LA", 29.9511, -90.0715),
    ("nashville", "Nashville, TN", 36.1627, -86.7816),
    ("atlanta", "Atlanta, GA", 33.7490, -84.3880),
    ("miami", "Miami, FL", 25.7617, -80.1918),
    ("orlando", "Orlando, FL", 28.5383, -81.3792),
    ("new york", "New York, NY", 40.7128, -74.0060),
    ("new york city", "New York, NY", 40.7128, -74.0060),
    ("boston", "Boston, MA", 42.3601, -71.0589),
    ("philadelphia", "Philadelphia, PA", 39.9526, -75.1652),
    ("detroit", "Detroit, MI", 42.3314, -83.0458),
    ("washington dc", "Washington, DC", 38.9072, -77.0369),
    ("washington d c", "Washington, DC", 38.9072, -77.0369),
    ("vancouver", "Vancouver, BC", 49.2827, -123.1207),
    ("toronto", "Toronto, ON", 43.6532, -79.3832),
    ("montreal", "Montreal, QC", 45.5019, -73.5674),
    # --- parks & landmarks ---
    ("yosemite", "Yosemite National Park", 37.8651, -119.5383),
    ("grand canyon", "Grand Canyon National Park", 36.1069, -112.1129),
    ("yellowstone", "Yellowstone National Park", 44.4280, -110.5885),
    ("grand teton", "Grand Teton National Park", 43.7904, -110.6818),
    ("zion", "Zion National Park", 37.2982, -113.0263),
    ("bryce canyon", "Bryce Canyon National Park", 37.5930, -112.1871),
    ("arches", "Arches National Park", 38.7331, -109.5925),
    ("joshua tree", "Joshua Tree National Park", 33.8734, -115.9010),
    ("death valley", "Death Valley National Park", 36.5054, -116.9347),
    ("sequoia", "Sequoia National Park", 36.4864, -118.5658),
    ("glacier national park", "Glacier National Park", 48.7596, -113.7870),
    ("rocky mountain", "Rocky Mountain National Park", 40.3428, -105.6836),
    ("mount rainier", "Mount Rainier National Park", 46.8523, -121.7603),
    ("mt rainier", "Mount Rainier National Park", 46.8523, -121.7603),
    ("crater lake", "Crater Lake National Park", 42.9446, -122.1090),
    ("great smoky mountains", "Great Smoky Mountains National Park", 35.6118, -83.4895),
    ("smoky mountains", "Great Smoky Mountains National Park", 35.6118, -83.4895),
    ("acadia", "Acadia National Park", 44.3386, -68.2733),
    ("everglades", "Everglades National Park", 25.2866, -80.8987),
    ("mount rushmore", "Mount Rushmore", 43.8791, -103.4591),
    ("niagara falls", "Niagara Falls", 43.0962, -79.0377),
    ("lake tahoe", "Lake Tahoe", 39.0968, -120.0324),
    ("big sur", "Big Sur, CA", 36.2704, -121.8081),
    ("monterey", "Monterey, CA", 36.6002, -121.8947),
    ("santa barbara", "Santa Barbara, CA", 34.4208, -119.6982),
    ("napa", "Napa, CA", 38.2975, -122.2869),
    ("moab", "Moab, UT", 38.5733, -109.5498),
    ("sedona", "Sedona, AZ", 34.8697, -111.7610),
    ("key west", "Key West, FL", 24.5551, -81.7800),
    ("savannah", "Savannah, GA", 32.0809, -81.0912),
    ("charleston", "Charleston, SC", 32.7765, -79.9311),
    ("asheville", "Asheville, NC", 35.5951, -82.5515),
    # --- a few world cities ---
    ("london", "London, UK", 51.5074, -0.1278),
    ("paris", "Paris, France", 48.8566, 2.3522),
    ("rome", "Rome, Italy", 41.9028, 12.4964),
    ("barcelona", "Barcelona, Spain", 41.3851, 2.1734),
    ("amsterdam", "Amsterdam, Netherlands", 52.3676, 4.9041),
    ("tokyo", "Tokyo, Japan", 35.6762, 139.6503),
    ("sydney", "Sydney, Australia", -33.8688, 151.2093),
    # --- more US cities ---
    ("san antonio", "San Antonio, TX", 29.4241, -98.4936),
    ("fort worth", "Fort Worth, TX", 32.7555, -97.3308),
    ("tucson", "Tucson, AZ", 32.2226, -110.9747),
    ("el paso", "El Paso, TX", 31.7619, -106.4850),
    ("oklahoma city", "Oklahoma City, OK", 35.4676, -97.5164),
    ("tulsa", "Tulsa, OK", 36.1540, -95.9928),
    ("omaha", "Omaha, NE", 41.2565, -95.9345),
    ("memphis", "Memphis, TN", 35.1495, -90.0490),
    ("louisville", "Louisville, KY", 38.2527, -85.7585),
    ("indianapolis", "Indianapolis, IN", 39.7684, -86.1581),
    ("columbus", "Columbus, OH", 39.9612, -82.9988),
    ("cincinnati", "Cincinnati, OH", 39.1031, -84.5120),
    ("cleveland", "Cleveland, OH", 41.4993, -81.6944),
    ("pittsburgh", "Pittsburgh, PA", 40.4406, -79.9959),
    ("milwaukee", "Milwaukee, WI", 43.0389, -87.9065),
    ("tampa", "Tampa, FL", 27.9506, -82.4572),
    ("jacksonville", "Jacksonville, FL", 30.3322, -81.6557),
    ("raleigh", "Raleigh, NC", 35.7796, -78.6382),
    ("richmond", "Richmond, VA", 37.5407, -77.4360),
    ("buffalo", "Buffalo, NY", 42.8864, -78.8784),
    ("spokane", "Spokane, WA", 47.6588, -117.4260),
    ("eugene", "Eugene, OR", 44.0521, -123.0868),
    ("palm springs", "Palm Springs, CA", 33.8303, -116.5453),
    ("santa cruz", "Santa Cruz, CA", 36.9741, -122.0308),
    ("jackson hole", "Jackson Hole, WY", 43.4799, -110.7624),
    ("estes park", "Estes Park, CO", 40.3772, -105.5217),
    ("gatlinburg", "Gatlinburg, TN", 35.7143, -83.5102),
    # --- more parks & landmarks ---
    ("olympic national park", "Olympic National Park", 47.8021, -123.6044),
    ("north cascades", "North Cascades National Park", 48.7718, -121.2985),
    ("redwood", "Redwood National Park", 41.2132, -124.0046),
    ("kings canyon", "Kings Canyon National Park", 36.8879, -118.5551),
    ("capitol reef", "Capitol Reef National Park", 38.3670, -111.2615),
    ("canyonlands", "Canyonlands National Park", 38.3269, -109.8783),
    ("mesa verde", "Mesa Verde National Park", 37.2309, -108.4618),
    ("badlands", "Badlands National Park", 43.8554, -101.9777),
    ("shenandoah", "Shenandoah National Park", 38.5331, -78.3499),
    ("big bend", "Big Bend National Park", 29.1275, -103.2425),
    ("carlsbad caverns", "Carlsbad Caverns National Park", 32.1479, -104.5567),
    ("petrified forest", "Petrified Forest National Park", 34.9100, -109.8068),
    ("saguaro", "Saguaro National Park", 32.2967, -111.1666),
    ("lassen", "Lassen Volcanic National Park", 40.4977, -121.4207),
    ("devils tower", "Devils Tower", 44.5902, -104.7146),
    ("horseshoe bend", "Horseshoe Bend", 36.8791, -111.5104),
    ("hoover dam", "Hoover Dam", 36.0161, -114.7377),
    ("antelope canyon", "Antelope Canyon", 36.8619, -111.3743),
    ("mount st helens", "Mount St. Helens", 46.1912, -122.1944),
    ("mt st helens", "Mount St. Helens", 46.1912, -122.1944),
    ("outer banks", "Outer Banks, NC", 35.5582, -75.4665),
    ("cape cod", "Cape Cod, MA", 41.6688, -70.2962),
    # --- more world cities ---
    ("berlin", "Berlin, Germany", 52.5200, 13.4050),
    ("madrid", "Madrid, Spain", 40.4168, -3.7038),
    ("lisbon", "Lisbon, Portugal", 38.7223, -9.1393),
    ("dublin", "Dublin, Ireland", 53.3498, -6.2603),
    ("edinburgh", "Edinburgh, UK", 55.9533, -3.1883),
    ("munich", "Munich, Germany", 48.1351, 11.5820),
    ("vienna", "Vienna, Austria", 48.2082, 16.3738),
    ("prague", "Prague, Czechia", 50.0755, 14.4378),
    ("venice", "Venice, Italy", 45.4408, 12.3155),
    ("florence", "Florence, Italy", 43.7696, 11.2558),
    ("mexico city", "Mexico City, Mexico", 19.4326, -99.1332),
    ("cancun", "Cancún, Mexico", 21.1619, -86.8515),
)

_GAZETTEER_BY_KEY: dict[str, tuple[str, float, float]] = {
    key: (display, lat, lng) for key, display, lat, lng in _GAZETTEER
}
# Longest keys first so "grand canyon" beats a hypothetical "grand" partial.
_KEYS_BY_LENGTH: tuple[str, ...] = tuple(
    sorted(_GAZETTEER_BY_KEY, key=len, reverse=True)
)


def _normalize(text: str) -> str:
    """Lowercase, drop a trailing region qualifier, and strip punctuation."""

    head = re.split(r"[,/|]", text, maxsplit=1)[0]
    head = head.lower()
    head = re.sub(r"[^a-z0-9 ]+", " ", head)
    return re.sub(r"\s+", " ", head).strip()


@lru_cache(maxsize=512)
def _lookup_local(text: str) -> GeocodeResult | None:
    norm = _normalize(text)
    if not norm:
        return None

    hit = _GAZETTEER_BY_KEY.get(norm)
    if hit is not None:
        display, lat, lng = hit
        return GeocodeResult(name=display, coord=Coordinate(lat=lat, lng=lng))

    # Partial match: a known place name appears as a run of whole words inside
    # the query (e.g. "yosemite national park" -> "yosemite"). Matching on word
    # boundaries — not raw substrings — avoids mislocating "Bend" to "Horseshoe
    # Bend" or "Fresno" to "Reno". Longest keys are tried first.
    query_words = norm.split()
    for key in _KEYS_BY_LENGTH:
        key_words = key.split()
        span = len(key_words)
        for i in range(len(query_words) - span + 1):
            if query_words[i : i + span] == key_words:
                display, lat, lng = _GAZETTEER_BY_KEY[key]
                return GeocodeResult(name=display, coord=Coordinate(lat=lat, lng=lng))
    return None


def _nominatim_enabled() -> bool:
    return os.getenv("ROADTRIP_USE_NOMINATIM", "").strip().lower() in ("1", "true", "yes")


@lru_cache(maxsize=512)
def _lookup_nominatim(text: str) -> GeocodeResult | None:
    params = urllib.parse.urlencode({"q": text, "format": "json", "limit": 1})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "roadTrip-planner/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if not payload:
        return None
    top = payload[0]
    try:
        return GeocodeResult(
            name=top.get("display_name", text).split(",")[0].strip() or text,
            coord=Coordinate(lat=float(top["lat"]), lng=float(top["lon"])),
        )
    except (KeyError, ValueError, TypeError):
        return None


async def geocode(text: str) -> GeocodeResult | None:
    """Resolve ``text`` to a :class:`GeocodeResult`, or ``None`` if unknown."""

    text = (text or "").strip()
    if not text:
        return None

    local = _lookup_local(text)
    if local is not None:
        return local

    if _nominatim_enabled():
        # Network call off the event loop so we don't block other requests.
        return await asyncio.to_thread(_lookup_nominatim, text)
    return None
