"""End-to-end tests for the heuristic planner."""

from __future__ import annotations

import asyncio

from backend.app.planner import plan_trip
from backend.app.schemas import Pace, PlanRequest, PlanResponse, StopKind


def _plan(**kwargs) -> PlanResponse:
    return asyncio.run(plan_trip(PlanRequest(**kwargs)))


def test_origin_and_destination() -> None:
    plan = _plan(origin="San Francisco", destination="Los Angeles", days=2)
    assert plan.start_name.startswith("San Francisco")
    assert plan.end_name.startswith("Los Angeles")
    assert plan.distance_meters > 0
    assert plan.expected_travel_time_seconds > 0
    assert plan.costs.total_usd > 0
    assert plan.stops
    assert "→" in plan.title


def test_idea_parsing_from_to() -> None:
    plan = _plan(idea="Drive from Seattle to Portland", days=2)
    assert plan.start_name.startswith("Seattle")
    assert plan.end_name.startswith("Portland")


def test_idea_destination_only() -> None:
    plan = _plan(idea="Visit Grand Canyon", days=2)
    assert "Grand Canyon" in plan.end_name


def test_direction_only_trip_projects_offset() -> None:
    plan = _plan(origin="Denver", direction="north", days=3)
    # Heading north should land north of Denver's latitude (~39.7).
    assert plan.end_coord.lat > 39.7
    assert "Wandering" in plan.tags


def test_direction_reach_scales_with_days() -> None:
    short = _plan(origin="Denver", direction="west", days=2)
    long = _plan(origin="Denver", direction="west", days=6)
    # A longer wander must cover meaningfully more ground than a short one.
    assert long.distance_meters > short.distance_meters
    # A 6-day "head west" should be a substantial trip, not a token hop.
    assert long.distance_meters > 800_000  # > 800 km


def test_single_day_trip_has_one_headline_stop() -> None:
    plan = _plan(destination="Yosemite", days=1)
    assert len(plan.stops) == 1
    assert plan.stops[0].kind is StopKind.attraction


def test_multi_day_trip_inserts_lodging() -> None:
    plan = _plan(origin="San Francisco", destination="Seattle", days=3)
    assert any(s.kind is StopKind.lodging for s in plan.stops)


def test_packed_pace_adds_second_stops_and_tag() -> None:
    relaxed = _plan(origin="San Francisco", destination="Las Vegas", days=3, pace=Pace.relaxed)
    packed = _plan(origin="San Francisco", destination="Las Vegas", days=3, pace=Pace.packed)
    assert len(packed.stops) > len(relaxed.stops)
    assert "Packed" in packed.tags
    assert "Relaxed" in relaxed.tags


def test_unknown_origin_produces_warning() -> None:
    plan = _plan(origin="Zzqxville Nowhere", destination="Denver", days=2)
    assert any("Zzqxville" in w for w in plan.warnings)


def test_response_serializes_to_json() -> None:
    plan = _plan(idea="weekend near Lake Tahoe", days=2)
    blob = plan.model_dump_json()
    assert "costs" in blob and "stops" in blob
