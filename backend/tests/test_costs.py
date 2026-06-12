"""Tests for distance and cost math."""

from __future__ import annotations

from backend.app.costs import estimate_costs, haversine_meters
from backend.app.schemas import Coordinate, PlanStop, StopKind


def _stop(kind: StopKind, day: int = 1) -> PlanStop:
    return PlanStop(day=day, order=0, name=kind.value, kind=kind, coord=Coordinate(lat=0, lng=0))


def test_haversine_zero_distance() -> None:
    assert haversine_meters(40.0, -100.0, 40.0, -100.0) == 0.0


def test_haversine_sf_to_la_is_about_559km() -> None:
    meters = haversine_meters(37.7749, -122.4194, 34.0522, -118.2437)
    km = meters / 1000.0
    assert 540.0 < km < 575.0


def test_estimate_costs_components_are_positive() -> None:
    stops = [
        _stop(StopKind.attraction),
        _stop(StopKind.lodging),
        _stop(StopKind.scenic, day=2),
    ]
    costs = estimate_costs(
        distance_meters=500_000.0, days=3, party_size=2, stops=stops
    )
    assert costs.fuel_usd > 0
    assert costs.lodging_usd > 0  # one lodging stop present
    assert costs.food_usd > 0
    assert costs.activities_usd > 0  # attraction + scenic are paid stops
    assert costs.total_usd == round(
        costs.fuel_usd + costs.lodging_usd + costs.food_usd + costs.activities_usd, 2
    )
    assert costs.assumptions  # transparency: show the work


def test_lodging_falls_back_to_nights_when_no_lodging_stops() -> None:
    # No lodging stop in the itinerary -> fall back to days-1 nights.
    costs = estimate_costs(
        distance_meters=100_000.0, days=4, party_size=2, stops=[_stop(StopKind.attraction)]
    )
    assert costs.lodging_usd > 0


def test_single_day_trip_has_no_lodging() -> None:
    costs = estimate_costs(
        distance_meters=50_000.0, days=1, party_size=2, stops=[_stop(StopKind.attraction)]
    )
    assert costs.lodging_usd == 0.0


def test_per_person_scales_down_with_party_size() -> None:
    solo = estimate_costs(distance_meters=200_000.0, days=2, party_size=1, stops=[])
    duo = estimate_costs(distance_meters=200_000.0, days=2, party_size=2, stops=[])
    # Total goes up with more people, but per-person should not exceed solo.
    assert duo.total_usd > solo.total_usd
    assert duo.per_person_usd < solo.per_person_usd
