"""Async Python library for the Modbus interfaces of Weider heat pumps.

Each supported controller and register map has its own device class:
``WeiderWT16`` for the Modbus TCP map and ``WeiderWT16RTU`` for the RS485
(Modbus RTU) map.
"""

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
from .device import WeiderWT16, WeiderWT16RTU
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
    "WeiderWT16",
    "WeiderWT16RTU",
    "clean_error_text",
    "plausible_temperature",
    "sg_ready_mode",
]
