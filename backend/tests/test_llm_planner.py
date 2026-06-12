"""Tests for the LLM-backed planner — fully offline.

The Claude call (`_generate_itinerary`) and the enable check (`_llm_enabled`)
are isolated so they can be monkeypatched; the assembly logic is exercised
directly with a hand-built itinerary. No network, no API key required.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.app import llm_planner
from backend.app.llm_planner import (
    _LLMItinerary,
    _LLMStop,
    _assemble_response,
    _coerce_kind,
    plan_trip,
)
from backend.app.schemas import PlanRequest, StopKind


def _sample_itinerary() -> _LLMItinerary:
    return _LLMItinerary(
        title="SF to Yosemite",
        summary="A scenic two-day drive.",
        tags=["Road Trip", "Nature"],
        # Unknown to the gazetteer -> assembly trusts these coords.
        start_name="Zzqx Junction",
        start_lat=37.5,
        start_lng=-122.0,
        # Known to the gazetteer -> assembly overrides name + coords.
        end_name="Yosemite National Park",
        end_lat=37.86,
        end_lng=-119.53,
        stops=[
            _LLMStop(day=1, name="Golden Gate Bridge", kind="attraction",
                     lat=37.8199, lng=-122.4783, arrival_local="09:00",
                     duration_minutes=60, notes="Iconic span."),
            _LLMStop(day=1, name="Stockton", kind="lodging",
                     lat=37.9577, lng=-121.2908, arrival_local="19:00",
                     duration_minutes=600),
            # Unknown kind -> coerced to attraction.
            _LLMStop(day=2, name="Tunnel View", kind="sightseeing",
                     lat=37.7156, lng=-119.6770, duration_minutes=45),
            # Day past the trip length + out-of-range coords -> clamped.
            _LLMStop(day=9, name="Way Out There", kind="scenic",
                     lat=200.0, lng=-400.0, duration_minutes=30),
        ],
    )


def test_coerce_kind_maps_unknown_to_attraction() -> None:
    assert _coerce_kind("lodging") is StopKind.lodging
    assert _coerce_kind("SCENIC") is StopKind.scenic
    assert _coerce_kind("sightseeing") is StopKind.attraction
    assert _coerce_kind("") is StopKind.attraction


def test_assemble_response_builds_valid_plan() -> None:
    req = PlanRequest(idea="SF to Yosemite", days=2, party_size=2)
    plan = asyncio.run(_assemble_response(req, _sample_itinerary()))

    assert plan.source == "llm"
    # Unknown start kept as-is; known end corrected via gazetteer.
    assert plan.start_name == "Zzqx Junction"
    assert plan.end_name == "Yosemite National Park"
    assert plan.distance_meters > 0
    assert plan.expected_travel_time_seconds > 0
    assert plan.costs.total_usd > 0
    assert plan.costs.lodging_usd > 0  # the lodging stop is counted


def test_assemble_response_clamps_and_orders_stops() -> None:
    req = PlanRequest(idea="SF to Yosemite", days=2, party_size=2)
    plan = asyncio.run(_assemble_response(req, _sample_itinerary()))

    assert [s.day for s in plan.stops] == [1, 1, 2, 2]  # day 9 clamped to 2
    assert [s.order for s in plan.stops] == [0, 1, 0, 1]  # per-day ordering
    assert plan.stops[2].kind is StopKind.attraction  # "sightseeing" coerced
    # Out-of-range coordinates clamped into valid bounds.
    assert plan.stops[3].coord.lat == 90.0
    assert plan.stops[3].coord.lng == -180.0


def test_dispatcher_uses_heuristic_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(llm_planner, "_llm_enabled", lambda: False)
    plan = asyncio.run(plan_trip(PlanRequest(origin="San Francisco",
                                             destination="Los Angeles", days=2)))
    assert plan.source == "heuristic"


def test_dispatcher_uses_llm_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(llm_planner, "_llm_enabled", lambda: True)

    async def _fake_generate(req):
        return _sample_itinerary()

    monkeypatch.setattr(llm_planner, "_generate_itinerary", _fake_generate)
    plan = asyncio.run(plan_trip(PlanRequest(idea="SF to Yosemite", days=2)))
    assert plan.source == "llm"
    assert plan.stops


def test_dispatcher_falls_back_on_llm_error(monkeypatch) -> None:
    monkeypatch.setattr(llm_planner, "_llm_enabled", lambda: True)

    async def _boom(req):
        raise RuntimeError("network down")

    monkeypatch.setattr(llm_planner, "_generate_itinerary", _boom)
    plan = asyncio.run(plan_trip(PlanRequest(origin="Denver", direction="west", days=3)))
    assert plan.source == "heuristic"
    assert any("heuristic" in w for w in plan.warnings)


def test_dispatcher_falls_back_on_empty_itinerary(monkeypatch) -> None:
    monkeypatch.setattr(llm_planner, "_llm_enabled", lambda: True)

    async def _none(req):
        return None

    monkeypatch.setattr(llm_planner, "_generate_itinerary", _none)
    plan = asyncio.run(plan_trip(PlanRequest(destination="Yosemite", days=2)))
    assert plan.source == "heuristic"
    assert any("heuristic" in w for w in plan.warnings)


def test_llm_enabled_respects_env(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ROADTRIP_DISABLE_LLM", raising=False)
    assert llm_planner._llm_enabled() is False

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert llm_planner._llm_enabled() is True

    monkeypatch.setenv("ROADTRIP_DISABLE_LLM", "1")
    assert llm_planner._llm_enabled() is False
