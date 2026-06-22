"""Environment-overridable tuning knobs.

Lets a deployment tweak cost rates and routing assumptions without code changes
(e.g. ``docker run -e ROADTRIP_GAS_USD_PER_GALLON=4.25 ...``). Values are read at
call time so a process can be reconfigured without reimporting.
"""

from __future__ import annotations

import os


def env_float(name: str, default: float) -> float:
    """Return env var ``name`` as a float, or ``default`` if unset/invalid."""

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default
