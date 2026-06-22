"""Distance and cost math.

Deliberately transparent and deterministic: every dollar in the estimate traces
back to a named rate below, and every rate is echoed into
``CostBreakdown.assumptions`` so the app can show its work. When we later swap in
live fuel/lodging prices, only the constants here should change.
"""

from __future__ import annotations

import math
from typing import Iterable

from .config import env_float
from .schemas import CostBreakdown, PlanStop, StopKind

_EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius
_METERS_PER_MILE = 1609.344

# --- cost model knobs -------------------------------------------------------
# ``distance_meters`` is true road distance (from routing.py — OSRM or estimate).
_AVG_MPG = 27.0
_GAS_USD_PER_GALLON = 3.50
_LODGING_USD_PER_ROOM_NIGHT = 130.0
_TRAVELERS_PER_ROOM = 2
_FOOD_USD_PER_PERSON_DAY = 45.0
_ACTIVITY_USD_PER_PERSON = 25.0

# Stop kinds we charge an admission/activity fee for.
_PAID_STOP_KINDS = (StopKind.attraction, StopKind.scenic, StopKind.activity)


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters."""

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return _EARTH_RADIUS_M * c


def estimate_costs(
    *,
    distance_meters: float,
    days: int,
    party_size: int,
    stops: Iterable[PlanStop],
    round_trip: bool = False,
) -> CostBreakdown:
    """Build an itemised cost estimate for a trip.

    ``distance_meters`` is the full road distance to be driven (the caller adds a
    return leg for round trips), so fuel is computed straight off it. Lodging
    nights come from the itinerary's ``lodging`` stops when present (the planner
    inserts one per overnight); otherwise we fall back to ``days - 1`` nights.
    Rooms scale with party size.
    """

    stops = list(stops)
    party_size = max(1, int(party_size))
    days = max(1, int(days))

    # Rates default to the constants above; deployments override via env vars.
    mpg = env_float("ROADTRIP_AVG_MPG", _AVG_MPG)
    gas = env_float("ROADTRIP_GAS_USD_PER_GALLON", _GAS_USD_PER_GALLON)
    lodging_rate = env_float("ROADTRIP_LODGING_USD_PER_ROOM_NIGHT", _LODGING_USD_PER_ROOM_NIGHT)
    food_rate = env_float("ROADTRIP_FOOD_USD_PER_PERSON_DAY", _FOOD_USD_PER_PERSON_DAY)
    activity_rate = env_float("ROADTRIP_ACTIVITY_USD_PER_PERSON", _ACTIVITY_USD_PER_PERSON)

    road_meters = max(0.0, distance_meters)
    miles = road_meters / _METERS_PER_MILE
    gallons = miles / mpg
    fuel = gallons * gas

    lodging_nights = sum(1 for s in stops if s.kind is StopKind.lodging)
    if lodging_nights == 0:
        lodging_nights = max(days - 1, 0)
    rooms = max(1, math.ceil(party_size / _TRAVELERS_PER_ROOM))
    lodging = lodging_nights * rooms * lodging_rate

    food = days * party_size * food_rate

    paid_stops = sum(1 for s in stops if s.kind in _PAID_STOP_KINDS)
    activities = paid_stops * party_size * activity_rate

    total = fuel + lodging + food + activities
    per_person = total / party_size

    assumptions = [
        f"Fuel: ~{miles:,.0f} road miles at {mpg:.0f} mpg, "
        f"${gas:.2f}/gal ({'round trip' if round_trip else 'one-way'}).",
        f"Lodging: {lodging_nights} night(s) x {rooms} room(s) at "
        f"${lodging_rate:.0f}/room.",
        f"Food: {days} day(s) x {party_size} traveler(s) at "
        f"${food_rate:.0f}/person/day.",
        f"Activities: {paid_stops} paid stop(s) x {party_size} traveler(s) at "
        f"${activity_rate:.0f}/person.",
    ]

    return CostBreakdown(
        fuel_usd=round(fuel, 2),
        lodging_usd=round(lodging, 2),
        food_usd=round(food, 2),
        activities_usd=round(activities, 2),
        total_usd=round(total, 2),
        per_person_usd=round(per_person, 2),
        assumptions=assumptions,
    )
