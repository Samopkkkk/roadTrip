"""Routing — turn an ordered list of coordinates into road distance and time.

This module owns the one job of converting geometry into a drivable route:

- When OSRM is enabled (``ROADTRIP_USE_OSRM=1`` or a custom ``ROADTRIP_OSRM_URL``),
  it asks an OSRM server for real road distance/duration following actual roads,
  with a per-leg breakdown.
- Otherwise it falls back to a deterministic estimate: great-circle distance
  scaled by a road-winding factor, at an average driving speed. This keeps the
  app instant and offline, and tests reproducible.

Centralising this here means the road-distance factor lives in exactly one place
— ``costs.py`` now treats the distance it's given as true road distance, whether
that came from OSRM or this estimate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

from .costs import haversine_meters
from .schemas import Coordinate, RouteLeg

_AVG_DRIVE_MPH = 55.0
_METERS_PER_MILE = 1609.344
# Great-circle under-counts real driving; scale it up for the offline estimate.
_ROAD_DISTANCE_FACTOR = 1.25
_OSRM_TIMEOUT_SECONDS = 8.0
_DEFAULT_OSRM_URL = "https://router.project-osrm.org"


@dataclass(frozen=True)
class RouteResult:
    distance_meters: float
    duration_seconds: float
    legs: list[RouteLeg] = field(default_factory=list)
    source: str = "estimate"  # "osrm" or "estimate"


def _seconds_for(road_meters: float) -> float:
    return (road_meters / _METERS_PER_MILE) / _AVG_DRIVE_MPH * 3600.0


def estimate_route(waypoints: list[Coordinate]) -> RouteResult:
    """Offline, deterministic route estimate (great-circle x road factor)."""

    legs: list[RouteLeg] = []
    for a, b in zip(waypoints, waypoints[1:]):
        road = haversine_meters(a.lat, a.lng, b.lat, b.lng) * _ROAD_DISTANCE_FACTOR
        legs.append(
            RouteLeg(
                distance_meters=round(road, 1),
                duration_seconds=round(_seconds_for(road), 0),
            )
        )
    return RouteResult(
        distance_meters=round(sum(l.distance_meters for l in legs), 1),
        duration_seconds=round(sum(l.duration_seconds for l in legs), 0),
        legs=legs,
        source="estimate",
    )


def _osrm_base_url() -> str:
    return os.getenv("ROADTRIP_OSRM_URL", "").strip() or _DEFAULT_OSRM_URL


def _osrm_enabled() -> bool:
    if os.getenv("ROADTRIP_OSRM_URL", "").strip():
        return True
    return os.getenv("ROADTRIP_USE_OSRM", "").strip().lower() in ("1", "true", "yes")


async def _osrm_route(waypoints: list[Coordinate]) -> RouteResult | None:
    """Ask an OSRM server for a real driving route. Returns None on any failure."""

    coords = ";".join(f"{wp.lng},{wp.lat}" for wp in waypoints)
    url = f"{_osrm_base_url()}/route/v1/driving/{coords}"
    params = {"overview": "false", "steps": "false", "annotations": "false"}
    try:
        async with httpx.AsyncClient(timeout=_OSRM_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return None

    if payload.get("code") != "Ok" or not payload.get("routes"):
        return None
    route = payload["routes"][0]
    try:
        legs = [
            RouteLeg(
                distance_meters=round(float(leg["distance"]), 1),
                duration_seconds=round(float(leg["duration"]), 0),
            )
            for leg in route.get("legs", [])
        ]
        return RouteResult(
            distance_meters=round(float(route["distance"]), 1),
            duration_seconds=round(float(route["duration"]), 0),
            legs=legs,
            source="osrm",
        )
    except (KeyError, ValueError, TypeError):
        return None


async def compute_route(waypoints: list[Coordinate]) -> RouteResult:
    """Best route for ``waypoints``: real (OSRM) when enabled, else estimated."""

    if len(waypoints) < 2:
        return RouteResult(distance_meters=0.0, duration_seconds=0.0, legs=[], source="estimate")

    if _osrm_enabled():
        osrm = await _osrm_route(waypoints)
        if osrm is not None:
            return osrm

    return estimate_route(waypoints)


def named_legs(result: RouteResult, names: list[str]) -> list[RouteLeg]:
    """Attach from/to place names to a route's legs (best-effort).

    Falls back to the unnamed legs if the name list doesn't line up with the
    leg count (which would mean a routing quirk we shouldn't guess around).
    """

    if len(names) != len(result.legs) + 1:
        return list(result.legs)
    return [
        RouteLeg(
            from_name=names[i],
            to_name=names[i + 1],
            distance_meters=leg.distance_meters,
            duration_seconds=leg.duration_seconds,
        )
        for i, leg in enumerate(result.legs)
    ]
