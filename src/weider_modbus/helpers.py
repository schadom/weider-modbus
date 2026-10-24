"""Interpretation of WT16 values that the raw registers do not carry."""

from __future__ import annotations

from enum import StrEnum

from .const import MAX_PLAUSIBLE_TEMPERATURE, MIN_PLAUSIBLE_TEMPERATURE


def plausible_temperature(value: float | None) -> float | None:
    """Return the temperature, or ``None`` if it is a placeholder value.

    The device reports a placeholder (for example 3276.7) for a temperature
    sensor that is not connected.
    """
    if value is None or MIN_PLAUSIBLE_TEMPERATURE <= value <= MAX_PLAUSIBLE_TEMPERATURE:
        return value
    return None


def clean_error_text(value: str | None) -> str | None:
    """Return the device's error text without padding, or ``None`` if no error.

    The device pads the 16-register text with null characters or spaces, so
    "no error" arrives as padding only.
    """
    if value is None:
        return None
    text = " ".join(value.replace("\x00", " ").split())
    return text or None


class SgReadyMode(StrEnum):
    """SG Ready operating states (Betriebszustände)."""

    UTILITY_BLOCK = "bz1_utility_block"
    NORMAL = "bz2_normal"
    INCREASED = "bz3_increased"
    START = "bz4_start"


def sg_ready_mode(
    utility_block: bool | None, sg_ready_1: bool | None, sg_ready_2: bool | None
) -> SgReadyMode | None:
    """Return the SG Ready operating state for the given input states.

    The utility company block always means BZ1. Otherwise SG Ready 1 and 2
    select the state: only SG Ready 2 on is BZ3, only SG Ready 1 on is BZ4, and
    anything else is BZ2. A missing utility block reading counts as no block;
    missing SG Ready readings make the state unknown.
    """
    if utility_block:
        return SgReadyMode.UTILITY_BLOCK
    if sg_ready_1 is None or sg_ready_2 is None:
        return None
    if sg_ready_2 and not sg_ready_1:
        return SgReadyMode.INCREASED
    if sg_ready_1 and not sg_ready_2:
        return SgReadyMode.START
    return SgReadyMode.NORMAL
