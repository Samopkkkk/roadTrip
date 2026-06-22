"""Tests for the routing module — offline estimate + mocked OSRM path."""

from __future__ import annotations

import asyncio

from backend.app import routing
from backend.app.costs import haversine_meters
from backend.app.routing import RouteResult, compute_route, estimate_route, named_legs
from backend.app.schemas import Coordinate, RouteLeg

_SF = Coordinate(lat=37.7749, lng=-122.4194)
_LA = Coordinate(lat=34.0522, lng=-118.2437)


def test_estimate_route_applies_road_factor() -> None:
    route = estimate_route([_SF, _LA])
    gc = haversine_meters(_SF.lat, _SF.lng, _LA.lat, _LA.lng)
    assert len(route.legs) == 1
    assert route.source == "estimate"
    # Road distance should exceed straight-line by roughly the 1.25 factor.
    assert route.distance_meters > gc
    assert 1.2 < route.distance_meters / gc < 1.3
    assert route.duration_seconds > 0


def test_estimate_route_leg_count() -> None:
    route = estimate_route([_SF, _LA, _SF])
    assert len(route.legs) == 2
    assert route.distance_meters == round(
        sum(l.distance_meters for l in route.legs), 1
    )


def test_route_estimate_is_env_tunable(monkeypatch) -> None:
    base = estimate_route([_SF, _LA])
    monkeypatch.setenv("ROADTRIP_ROAD_DISTANCE_FACTOR", "2.0")
    monkeypatch.setenv("ROADTRIP_AVG_DRIVE_MPH", "30")
    tuned = estimate_route([_SF, _LA])
    assert tuned.distance_meters > base.distance_meters  # larger road factor
    assert tuned.duration_seconds > base.duration_seconds  # slower + farther


def test_compute_route_offline_uses_estimate() -> None:
    route = asyncio.run(compute_route([_SF, _LA]))
    assert route.source == "estimate"
    assert route.distance_meters > 0


def test_compute_route_too_few_waypoints() -> None:
    route = asyncio.run(compute_route([_SF]))
    assert route.distance_meters == 0.0
    assert route.legs == []


def test_named_legs_attaches_names() -> None:
    route = estimate_route([_SF, _LA])
    legs = named_legs(route, ["San Francisco", "Los Angeles"])
    assert legs[0].from_name == "San Francisco"
    assert legs[0].to_name == "Los Angeles"


def test_named_legs_falls_back_on_mismatch() -> None:
    route = estimate_route([_SF, _LA])
    legs = named_legs(route, ["only-one-name"])  # wrong length
    assert legs[0].from_name is None


def test_compute_route_uses_osrm_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(routing, "_osrm_enabled", lambda: True)

    async def _fake_osrm(waypoints):
        return RouteResult(
            distance_meters=999.0,
            duration_seconds=42.0,
            legs=[RouteLeg(distance_meters=999.0, duration_seconds=42.0)],
            source="osrm",
        )

    monkeypatch.setattr(routing, "_osrm_route", _fake_osrm)
    route = asyncio.run(compute_route([_SF, _LA]))
    assert route.source == "osrm"
    assert route.distance_meters == 999.0


def test_compute_route_falls_back_when_osrm_fails(monkeypatch) -> None:
    monkeypatch.setattr(routing, "_osrm_enabled", lambda: True)

    async def _fail(waypoints):
        return None

    monkeypatch.setattr(routing, "_osrm_route", _fail)
    route = asyncio.run(compute_route([_SF, _LA]))
    assert route.source == "estimate"
    assert route.distance_meters > 0
