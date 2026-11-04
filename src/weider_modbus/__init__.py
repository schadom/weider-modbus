"""Async Python library for the Modbus interfaces of Weider heat pumps.

Each supported controller and register map has its own device class:
``WeiderWT16TCP`` for the Modbus TCP map and ``WeiderWT16RTU`` for the RS485
(Modbus RTU) map.
"""

from __future__ import annotations

import warnings
from typing import Any

from .components import DigitalInputs, Measurements, Settings
from .const import (
    HOT_WATER_TARGET_MAX,
    HOT_WATER_TARGET_MIN,
    MANUFACTURER,
    MAX_PLAUSIBLE_TEMPERATURE,
    MIN_PLAUSIBLE_TEMPERATURE,
    MODEL,
    ROOM_TARGET_MAX,
    ROOM_TARGET_MIN,
    TARGET_STEP,
)
from .device import WeiderWT16RTU, WeiderWT16TCP
from .helpers import SgReadyMode, clean_error_text, plausible_temperature, sg_ready_mode
from .rtu import RtuDigitalInputs, RtuMeasurements, RtuSettings

__all__ = [
    "HOT_WATER_TARGET_MAX",
    "HOT_WATER_TARGET_MIN",
    "MANUFACTURER",
    "MAX_PLAUSIBLE_TEMPERATURE",
    "MIN_PLAUSIBLE_TEMPERATURE",
    "MODEL",
    "ROOM_TARGET_MAX",
    "ROOM_TARGET_MIN",
    "TARGET_STEP",
    "DigitalInputs",
    "Measurements",
    "RtuDigitalInputs",
    "RtuMeasurements",
    "RtuSettings",
    "Settings",
    "SgReadyMode",
    "WeiderWT16RTU",
    "WeiderWT16TCP",
    "clean_error_text",
    "plausible_temperature",
    "sg_ready_mode",
]


def __getattr__(name: str) -> Any:
    """Keep the old ``WeiderWT16`` name working, with a deprecation warning."""
    if name == "WeiderWT16":
        warnings.warn(
            "WeiderWT16 is deprecated and will be removed in weider-modbus 1.0; "
            "use WeiderWT16TCP instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return WeiderWT16TCP
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
