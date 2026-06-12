"""Heuristic trip planner.

Given a free-form idea (plus optional anchors), produce a structured plan with
coords, stops, and costs. This is the deterministic fallback used when no
ANTHROPIC_API_KEY is configured — and it's also what the iOS app sees on first
launch before any LLM cost. The LLM-backed planner (see TODO in task #5) will
produce richer stop lists; we'll keep this module as the source of truth for
distance math, cost math, and schema shape.
"""

from __future__ import annotations

import math
from typing import Iterable

from .costs import estimate_costs
from .geocode import geocode
from .routing import compute_route, named_legs
from .schemas import (
    Coordinate,
    CostBreakdown,
    PlanRequest,
    PlanResponse,
    PlanStop,
    StopKind,
)


async def plan_trip(req: PlanRequest) -> PlanResponse:
    origin_text, destination_text = _resolve_anchors(req)
    warnings: list[str] = []

    origin_geo = await geocode(origin_text) if origin_text else None
    if origin_geo is None and origin_text:
        warnings.append(f"Couldn't locate origin '{origin_text}'.")

    destination_geo = await geocode(destination_text) if destination_text else None
    destination_resolved = destination_geo is not None
    if destination_geo is None and destination_text:
        warnings.append(
            f"Couldn't locate destination '{destination_text}', "
            "using direction hint instead."
        )
    if destination_geo is None:
        provisional = origin_geo.coord if origin_geo else _fallback_origin().coord
        destination_geo = _fallback_destination(provisional, req)

    # Decide the origin. If the user never gave a start (and isn't just wandering
    # a direction), base the trip at the destination instead of the geographic
    # centre of the map — the app supplies the traveler's real location to route
    # there. This avoids absurd "1,800 km from Current location" estimates.
    origin_assumed = origin_geo is None
    based_at = False
    if origin_geo is None:
        if req.direction is None and destination_resolved:
            origin_geo = _based_at(destination_geo)
            based_at = True
            warnings.append(
                f"No starting point given — planning around {destination_geo.name}. "
                "Add your origin to include the drive there."
            )
        else:
            origin_geo = _fallback_origin()
            warnings.append("No starting point given — using a placeholder location.")

    route_coords = [origin_geo.coord, destination_geo.coord]
    route_names = [origin_geo.name, destination_geo.name]
    if req.round_trip:
        route_coords.append(origin_geo.coord)
        route_names.append(origin_geo.name)
    route = await compute_route(route_coords)
    distance_meters = route.distance_meters
    expected_travel_seconds = route.duration_seconds
    legs = named_legs(route, route_names)

    stops = _build_stop_skeleton(
        req=req,
        origin=origin_geo,
        destination=destination_geo,
    )

    costs: CostBreakdown = estimate_costs(
        distance_meters=distance_meters,
        days=req.days,
        party_size=req.party_size,
        stops=stops,
        round_trip=req.round_trip,
    )

    title = _build_title(origin_geo.name, destination_geo.name, req, based_at)
    summary = _build_summary(
        req=req,
        origin=origin_geo.name,
        destination=destination_geo.name,
        distance_meters=distance_meters,
        stops=stops,
        costs=costs,
        based_at=based_at,
    )
    tags = _build_tags(req)

    return PlanResponse(
        title=title,
        summary=summary,
        tags=tags,
        start_name=origin_geo.name,
        start_coord=origin_geo.coord,
        end_name=destination_geo.name,
        end_coord=destination_geo.coord,
        distance_meters=round(distance_meters, 1),
        expected_travel_time_seconds=round(expected_travel_seconds, 0),
        stops=stops,
        legs=legs,
        costs=costs,
        source="heuristic",
        origin_assumed=origin_assumed,
        warnings=warnings,
    )


def _resolve_anchors(req: PlanRequest) -> tuple[str | None, str | None]:
    """Return (origin, destination_to_geocode).

    A bare `direction` ("north", "south", "Pacific Coast") is intentionally
    NOT returned for geocoding — it would land Nominatim on whatever obscure
    place happens to share the name. Direction-only trips are handled by
    `_fallback_destination`, which projects an offset from the origin.
    """

    origin = req.origin
    destination = req.destination or req.anchor_attraction
    parsed_origin, parsed_destination = _extract_endpoints_from_idea(req.idea)
    if origin is None:
        origin = parsed_origin
    if destination is None and req.direction is None:
        destination = parsed_destination
    return origin, destination


_TO_KEYWORDS = (" to ", " towards ", " heading to ")
_FROM_KEYWORDS = (" from ", " starting in ", " leaving from ")


def _extract_endpoints_from_idea(idea: str) -> tuple[str | None, str | None]:
    """Pull out origin and destination from natural language.

    Examples:
      "Weekend trip to Yosemite from San Francisco"
        -> ("San Francisco", "Yosemite")
      "Drive from Seattle to Portland"
        -> ("Seattle", "Portland")
      "Visit Mount Rainier"
        -> (None, "Mount Rainier")
    """

    text = idea.strip()
    if not text:
        return None, None

    lowered = f" {text.lower()} "

    def _find_split(haystack: str, kws: tuple[str, ...]) -> int | None:
        for kw in kws:
            idx = haystack.find(kw)
            if idx >= 0:
                return idx
        return None

    to_match = _find_split(lowered, _TO_KEYWORDS)
    from_match = _find_split(lowered, _FROM_KEYWORDS)

    origin = destination = None

    if to_match is not None and from_match is not None and from_match < to_match:
        from_kw = next(k for k in _FROM_KEYWORDS if k in lowered)
        to_kw = next(k for k in _TO_KEYWORDS if k in lowered)
        origin = text[from_match + len(from_kw) - 1 : to_match - 1].strip(" .,!?;:")
        destination = text[to_match + len(to_kw) - 1 :].strip(" .,!?;:")
    elif to_match is not None:
        to_kw = next(k for k in _TO_KEYWORDS if k in lowered)
        after_to = text[to_match + len(to_kw) - 1 :]
        after_lowered = f" {after_to.lower()} "
        from_in_after = _find_split(after_lowered, _FROM_KEYWORDS)
        if from_in_after is not None:
            from_kw = next(k for k in _FROM_KEYWORDS if k in after_lowered)
            destination = after_to[: from_in_after - 1].strip(" .,!?;:")
            origin = after_to[from_in_after + len(from_kw) - 1 :].strip(" .,!?;:")
        else:
            destination = after_to.strip(" .,!?;:")
    elif from_match is not None:
        from_kw = next(k for k in _FROM_KEYWORDS if k in lowered)
        origin = text[from_match + len(from_kw) - 1 :].strip(" .,!?;:")
    else:
        destination = text.strip(" .,!?;:")

    return (origin or None, destination or None)


def _fallback_origin() -> "GeocodeResult":
    from .geocode import GeocodeResult

    return GeocodeResult(
        name="Current location",
        coord=Coordinate(lat=39.5, lng=-98.35),
    )


def _based_at(destination: "GeocodeResult") -> "GeocodeResult":
    """Start the trip at the destination — used when no origin was provided."""

    from .geocode import GeocodeResult

    return GeocodeResult(name=destination.name, coord=destination.coord)


def _fallback_destination(origin: Coordinate, req: PlanRequest) -> "GeocodeResult":
    from .geocode import GeocodeResult

    dx, dy = _direction_offset(req.direction or req.idea, req.days, origin.lat)
    return GeocodeResult(
        name=(req.direction or "Open road").strip() or "Open road",
        coord=Coordinate(
            lat=max(min(origin.lat + dy, 70.0), -70.0),
            lng=max(min(origin.lng + dx, 179.0), -179.0),
        ),
    )


_DIRECTION_MILES_PER_DAY = 180.0  # far-point reach for an open-ended wander
_MILES_PER_DEG_LAT = 69.0


def _direction_offset(hint: str, days: int, origin_lat: float) -> tuple[float, float]:
    """Project a far-point offset ``(d_lng, d_lat)`` in degrees for a wander.

    The reach scales with trip length so "head west for 5 days" covers real
    ground instead of a token 4-degree hop. Longitude degrees are widened toward
    the poles (they're physically shorter there) so the resulting mileage is
    honest regardless of the origin's latitude.
    """

    h = hint.lower()
    reach_miles = max(1, days) * _DIRECTION_MILES_PER_DAY
    deg_lat = reach_miles / _MILES_PER_DEG_LAT
    cos_lat = max(0.2, math.cos(math.radians(origin_lat)))
    deg_lng = reach_miles / (_MILES_PER_DEG_LAT * cos_lat)

    dx = dy = 0.0
    if "north" in h:
        dy += deg_lat
    if "south" in h:
        dy -= deg_lat
    if "east" in h:
        dx += deg_lng
    if "west" in h:
        dx -= deg_lng
    if dx == 0.0 and dy == 0.0:
        dx = deg_lng  # no compass word found: drift east
    return dx, dy


def _build_stop_skeleton(
    *,
    req: PlanRequest,
    origin,
    destination,
) -> list[PlanStop]:
    """Place evenly-spaced waypoints along the great-circle line.

    Heuristic only — the LLM-backed planner replaces these with real POIs.
    """

    if req.days <= 1:
        return [
            PlanStop(
                day=1,
                order=0,
                name=destination.name,
                kind=StopKind.attraction,
                coord=destination.coord,
                arrival_local="11:00",
                duration_minutes=180,
                notes="Headline stop for the day.",
            )
        ]

    stops: list[PlanStop] = []
    segments = req.days
    for day in range(1, req.days + 1):
        t = day / (segments + 1)
        lat = origin.coord.lat + (destination.coord.lat - origin.coord.lat) * t
        lng = origin.coord.lng + (destination.coord.lng - origin.coord.lng) * t
        stops.append(
            PlanStop(
                day=day,
                order=0,
                name=f"Day {day} highlight",
                kind=StopKind.attraction,
                coord=Coordinate(lat=lat, lng=lng),
                arrival_local="11:00",
                duration_minutes=120,
                notes="Auto-suggested midpoint — swap with a real POI.",
            )
        )
        if req.pace == "packed":
            stops.append(
                PlanStop(
                    day=day,
                    order=1,
                    name=f"Day {day} second stop",
                    kind=StopKind.scenic,
                    coord=Coordinate(lat=lat, lng=lng),
                    arrival_local="15:00",
                    duration_minutes=90,
                )
            )
        if day < req.days:
            stops.append(
                PlanStop(
                    day=day,
                    order=99,
                    name=f"Overnight near day {day} area",
                    kind=StopKind.lodging,
                    coord=Coordinate(lat=lat, lng=lng),
                    arrival_local="19:30",
                    duration_minutes=600,
                )
            )

    stops.append(
        PlanStop(
            day=req.days,
            order=100,
            name=destination.name,
            kind=StopKind.attraction,
            coord=destination.coord,
            arrival_local="16:00",
            duration_minutes=180,
            notes="Final destination.",
        )
    )
    return stops


def _build_title(
    origin_name: str, destination_name: str, req: PlanRequest, based_at: bool = False
) -> str:
    if based_at:
        return f"Explore {destination_name}"
    if req.destination or req.anchor_attraction:
        return f"{origin_name} → {destination_name}"
    if req.direction:
        return f"{origin_name}: {req.direction.title()}"
    return f"{origin_name} → {destination_name}"


def _build_summary(
    *,
    req: PlanRequest,
    origin: str,
    destination: str,
    distance_meters: float,
    stops: Iterable[PlanStop],
    costs: CostBreakdown,
    based_at: bool = False,
) -> str:
    stop_count = sum(1 for _ in stops)
    if based_at:
        return (
            f"A {req.days}-day trip exploring {destination} with {stop_count} "
            f"suggested stops. Estimated total: ${costs.total_usd:,.0f} for "
            f"{req.party_size} traveler(s) (excludes the drive to get there)."
        )
    km = distance_meters / 1000
    return (
        f"A {req.days}-day, ~{km:,.0f} km trip from {origin} to {destination} "
        f"with {stop_count} suggested stops. "
        f"Estimated total: ${costs.total_usd:,.0f} for {req.party_size} traveler(s)."
    )


def _build_tags(req: PlanRequest) -> list[str]:
    tags: list[str] = []
    if req.days >= 5:
        tags.append("Road Trip")
    else:
        tags.append("Weekend")
    if req.pace == "relaxed":
        tags.append("Relaxed")
    if req.pace == "packed":
        tags.append("Packed")
    if req.anchor_attraction:
        tags.append("Bucket-list")
    if req.direction:
        tags.append("Wandering")
    return tags
