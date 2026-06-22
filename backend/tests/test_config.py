"""Tests for the env-overridable config helper."""

from __future__ import annotations

from backend.app.config import env_float


def test_env_float_missing_returns_default(monkeypatch) -> None:
    monkeypatch.delenv("ROADTRIP_TEST_RATE", raising=False)
    assert env_float("ROADTRIP_TEST_RATE", 3.5) == 3.5


def test_env_float_parses_value(monkeypatch) -> None:
    monkeypatch.setenv("ROADTRIP_TEST_RATE", "4.25")
    assert env_float("ROADTRIP_TEST_RATE", 1.0) == 4.25


def test_env_float_invalid_or_blank_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("ROADTRIP_TEST_RATE", "not-a-number")
    assert env_float("ROADTRIP_TEST_RATE", 1.0) == 1.0
    monkeypatch.setenv("ROADTRIP_TEST_RATE", "   ")
    assert env_float("ROADTRIP_TEST_RATE", 1.0) == 1.0
