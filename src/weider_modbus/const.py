"""Device facts for the Weider WT16."""

from __future__ import annotations

from typing import Final

MANUFACTURER: Final = "Weider"
MODEL: Final = "WT16"

# Allowed write ranges for the target temperatures, in °C (inclusive).
HOT_WATER_TARGET_MIN: Final = 15.0
HOT_WATER_TARGET_MAX: Final = 55.0
ROOM_TARGET_MIN: Final = 5.0
ROOM_TARGET_MAX: Final = 35.0
TARGET_STEP: Final = 0.5

# The device reports a placeholder value, such as 3276.7, for a temperature
# sensor that is not connected. Readings outside this range are treated as
# unknown. The range covers outdoor temperatures down to -45 °C and the hot
# gas temperature of the refrigerant circuit.
MIN_PLAUSIBLE_TEMPERATURE: Final = -45.0
MAX_PLAUSIBLE_TEMPERATURE: Final = 150.0
