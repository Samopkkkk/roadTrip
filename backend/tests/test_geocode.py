"""Tests for the offline gazetteer geocoder."""

from __future__ import annotations

import asyncio

from backend.app.geocode import geocode


def _geo(text: str):
    return asyncio.run(geocode(text))


def test_exact_city_match() -> None:
    res = _geo("San Francisco")
    assert res is not None
    assert "San Francisco" in res.name
    assert 37.0 < res.coord.lat < 38.5
    assert -123.0 < res.coord.lng < -122.0


def test_case_and_qualifier_insensitive() -> None:
    res = _geo("los angeles, ca")
    assert res is not None
    assert "Los Angeles" in res.name


def test_partial_match_into_known_anchor() -> None:
    res = _geo("Yosemite National Park")
    assert res is not None
    assert "Yosemite" in res.name


def test_empty_returns_none() -> None:
    assert _geo("") is None
    assert _geo("   ") is None


def test_unknown_place_returns_none_without_network() -> None:
    # Nominatim disabled by default, so a made-up place resolves to nothing.
    assert _geo("Zzqxville Nowhere 99999") is None
