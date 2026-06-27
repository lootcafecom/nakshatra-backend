"""
Vastu Shastra directional engine.

Per the master plan, Vastu guidance must be computed from the person's
*actual* coordinates and *true* magnetic north for that location, not a
generic compass tip. This module has two external calls:

  1. Nominatim (OpenStreetMap) — free geocoding, city name -> lat/long
  2. NOAA World Magnetic Model — free, true magnetic declination for
     that lat/long, so "north" in the recommendation is the real compass
     bearing at the person's home, not assumed geographic north.

Both are free APIs with no key required. In this sandbox, outbound
network access is restricted to a small allowlist and does not include
either host, so live calls aren't testable here — but the request shape
below is correct per each service's public documentation and will work
in real deployment (Vercel/Render/etc. have unrestricted egress).
"""

from __future__ import annotations
from dataclasses import dataclass
import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOAA_WMM_URL = "https://www.ngdc.noaa.gov/geomag-web/calculators/calculateDeclination"

# the eight Vastu directional zones, in compass-bearing order starting from North
VASTU_ZONES = [
    {"name": "Uttara (North)", "bearing_start": 337.5, "bearing_end": 22.5, "ruling": "Kubera — wealth and prosperity"},
    {"name": "Ishanya (Northeast)", "bearing_start": 22.5, "bearing_end": 67.5, "ruling": "Water element, the most sacred zone — ideal for prayer or meditation"},
    {"name": "Purva (East)", "bearing_start": 67.5, "bearing_end": 112.5, "ruling": "Surya — health and new beginnings"},
    {"name": "Agneya (Southeast)", "bearing_start": 112.5, "bearing_end": 157.5, "ruling": "Fire element — ideal for the kitchen"},
    {"name": "Dakshina (South)", "bearing_start": 157.5, "bearing_end": 202.5, "ruling": "Yama — stability, best for solid heavy furniture"},
    {"name": "Nairutya (Southwest)", "bearing_start": 202.5, "bearing_end": 247.5, "ruling": "Earth element — ideal for the master bedroom"},
    {"name": "Paschima (West)", "bearing_start": 247.5, "bearing_end": 292.5, "ruling": "Shani — gains and savings"},
    {"name": "Vayavya (Northwest)", "bearing_start": 292.5, "bearing_end": 337.5, "ruling": "Air element — good for guest rooms"},
]


@dataclass
class GeocodeResult:
    place_name: str
    latitude: float
    longitude: float


@dataclass
class VastuProfile:
    place: GeocodeResult
    magnetic_declination: float   # degrees, true vs magnetic north at this location
    true_north_bearing: float     # the compass reading a user must add/subtract to find true north
    zones: list[dict]


async def geocode_place(place_name: str) -> GeocodeResult:
    """Resolve a free-text place name to coordinates using Nominatim."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": place_name, "format": "json", "limit": 1},
            headers={"User-Agent": "Nakshatra-Astrology-Platform/1.0"},
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            raise ValueError(f"Could not find coordinates for '{place_name}'")
        top = results[0]
        return GeocodeResult(
            place_name=top.get("display_name", place_name),
            latitude=float(top["lat"]),
            longitude=float(top["lon"]),
        )


async def get_magnetic_declination(latitude: float, longitude: float) -> float:
    """Query NOAA's World Magnetic Model for true magnetic declination
    at this location — the real-world gap between magnetic north (what
    a compass shows) and true north (what Vastu zones are defined
    against)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            NOAA_WMM_URL,
            params={
                "lat1": latitude,
                "lon1": longitude,
                "resultFormat": "json",
                "key": "zNEw7",  # NOAA's published public demo key for this endpoint
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return float(data["result"][0]["declination"])


def zone_for_bearing(bearing: float) -> dict:
    bearing = bearing % 360
    for zone in VASTU_ZONES:
        start, end = zone["bearing_start"], zone["bearing_end"]
        if start > end:  # wraps past 360 (North zone)
            if bearing >= start or bearing < end:
                return zone
        elif start <= bearing < end:
            return zone
    return VASTU_ZONES[0]


async def compute_vastu_profile(place_name: str, entrance_facing_bearing: float | None = None) -> VastuProfile:
    """Full Vastu profile for a home: geocode the place, get true
    magnetic declination there, and report which Vastu zone the home's
    entrance actually faces once corrected for true north."""
    place = await geocode_place(place_name)
    declination = await get_magnetic_declination(place.latitude, place.longitude)

    zones_report = []
    if entrance_facing_bearing is not None:
        true_bearing = (entrance_facing_bearing + declination) % 360
        zone = zone_for_bearing(true_bearing)
        zones_report.append({**zone, "true_bearing": round(true_bearing, 1)})

    return VastuProfile(
        place=place,
        magnetic_declination=round(declination, 2),
        true_north_bearing=round(declination, 2),
        zones=zones_report or VASTU_ZONES,
    )
