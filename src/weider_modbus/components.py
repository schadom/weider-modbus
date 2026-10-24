"""Typed Modbus components of the Weider WT16."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import ClassVar, Final

from modbus_connection.exceptions import IllegalDataAddressError
from modbus_connection.model import (
    Component,
    NumberField,
    discrete_input,
    gauge,
    integer,
    string,
    uint32,
)

from .const import (
    HOT_WATER_TARGET_MAX,
    HOT_WATER_TARGET_MIN,
    ROOM_TARGET_MAX,
    ROOM_TARGET_MIN,
)

_LOGGER = logging.getLogger(__name__)


def _temperature(address: int) -> NumberField[float]:
    """Return the signed, 0.1-scaled WT16 temperature format.

    Outdoor, source and refrigerant temperatures go below 0 °C, which the
    device sends as two's complement (65516 is -2.0 °C).
    """
    return gauge(address, 0.1, unit="°C")


def _range_validator(minimum: float, maximum: float) -> Callable[[float], float]:
    """Return a write validator that rejects values outside [minimum, maximum]."""

    def validate(value: float) -> float:
        if not minimum <= value <= maximum:
            raise ValueError(
                f"{value} is outside the allowed range {minimum}..{maximum}"
            )
        return value

    return validate


def _target_temperature(
    address: int, minimum: float, maximum: float
) -> NumberField[float]:
    """Return a writable, unsigned, 0.1-scaled target temperature.

    The device only accepts function code 16 for these registers.
    """
    return gauge(
        address,
        0.1,
        signed=False,
        unit="°C",
        writable=_range_validator(minimum, maximum),
        force_fc16=True,
    )


_READERS: Final = {
    "input": "read_input_registers",
    "holding": "read_holding_registers",
    "discrete": "read_discrete_inputs",
    "coil": "read_coils",
}


async def _rejected_fields(
    component: Component, space: str, names: set[str]
) -> set[str]:
    """Read each field on its own and return those the device rejects."""
    read = getattr(component.modbus_unit, _READERS[space])
    rejected = set()
    for name in sorted(names):
        field = component.resolved_fields[name]
        try:
            await read(field.address, field.count)
        except IllegalDataAddressError:
            rejected.add(name)
    return rejected


async def _update_skipping_unsupported(
    component: Component,
    update: Callable[..., Awaitable[None]],
    space: str,
    optional: frozenset[str] | None,
    *,
    notify: bool,
) -> None:
    """Refresh a component, dropping optional fields the device rejects.

    If the device rejects a block of several fields, each field is read on its
    own to find the unsupported ones. Unsupported fields are skipped only if
    they are all optional (``optional=None`` treats all fields as optional).
    Anything else is a real error and propagates, so it is reported instead of
    hidden.
    """
    while True:
        try:
            await update(notify=notify)
            return
        except IllegalDataAddressError as err:
            block = err.block
            if block is None or block.space != space:
                raise
            unsupported = {
                name
                for name, field in component.resolved_fields.items()
                if field.address < block.address + block.count
                and block.address < field.address + field.count
            }
            if len(unsupported) > 1:
                unsupported = await _rejected_fields(component, space, unsupported)
            if not unsupported or (
                optional is not None and not unsupported <= optional
            ):
                raise
            addresses = sorted(
                component.resolved_fields[name].address for name in unsupported
            )
            component.restrict_fields(set(component.resolved_fields) - unsupported)
            _LOGGER.info(
                "Skipping unsupported %s %s at %s %s",
                "field" if len(unsupported) == 1 else "fields",
                ", ".join(sorted(unsupported)),
                "address" if len(addresses) == 1 else "addresses",
                ", ".join(map(str, addresses)),
            )


class Measurements(Component):
    """Read-only WT16 input registers (function code 04)."""

    register_space = "input"
    # max_gap = 1 merges directly adjacent registers only, never across a gap.
    max_gap = 1
    max_span = 50

    hot_water_temperature = _temperature(13)
    flow_target_temperature = _temperature(14)
    outdoor_temperature = _temperature(15)
    buffer_temperature = _temperature(16)
    mixer_temperature = _temperature(17)
    reserve_temperature_1 = _temperature(18)
    reserve_temperature_2 = _temperature(19)
    reserve_temperature_3 = _temperature(20)
    defrost_temperature = _temperature(21)
    flow_temperature = _temperature(25)
    return_temperature = _temperature(26)
    source_inlet_temperature = _temperature(27)
    source_outlet_temperature = _temperature(28)
    superheat = _temperature(29)
    evaporation_temperature = _temperature(31)
    condensation_temperature = _temperature(33)
    evaporator_temperature = _temperature(35)
    suction_gas_temperature = _temperature(36)
    hot_gas_temperature = _temperature(37)
    volume_flow = gauge(44, 0.001, signed=False, unit="m³/h")
    room_temperature = _temperature(724)
    mixer_position = integer(736, signed=False)
    last_pump_runtime = uint32(60164, unit="min")
    last_hot_water_runtime = uint32(60168, unit="min")
    active_error = string(63000, 16)

    # Registers that some firmware versions do not provide.
    OPTIONAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "room_temperature",
            "mixer_position",
            "last_pump_runtime",
            "last_hot_water_runtime",
            "active_error",
        }
    )

    async def async_update(self, *, notify: bool = True) -> None:
        """Refresh measurements, skipping optional registers this device rejects."""
        await _update_skipping_unsupported(
            self, super().async_update, "input", self.OPTIONAL_FIELDS, notify=notify
        )


class Settings(Component):
    """Writable WT16 holding registers (function codes 03/16)."""

    max_gap = 0
    max_span = 50

    hot_water_target_temperature = _target_temperature(
        1, HOT_WATER_TARGET_MIN, HOT_WATER_TARGET_MAX
    )
    room_target_temperature = _target_temperature(723, ROOM_TARGET_MIN, ROOM_TARGET_MAX)

    # Installations without a room sensor may not provide the room target.
    OPTIONAL_FIELDS: ClassVar[frozenset[str]] = frozenset({"room_target_temperature"})

    async def async_update(self, *, notify: bool = True) -> None:
        """Refresh settings, skipping optional registers this device rejects."""
        await _update_skipping_unsupported(
            self, super().async_update, "holding", self.OPTIONAL_FIELDS, notify=notify
        )


class DigitalInputs(Component):
    """WT16 discrete inputs (function code 02)."""

    # max_gap = 1 merges directly adjacent inputs only, never across a gap.
    max_gap = 1
    max_span = 50

    flow_switch_1 = discrete_input(45)
    flow_switch_2 = discrete_input(69)
    compressor = discrete_input(679)
    heating_pump = discrete_input(680)
    source_pump = discrete_input(681)
    mixer_pump = discrete_input(682)
    hot_water_pump = discrete_input(685)
    remote_fault = discrete_input(686)
    four_way_valve = discrete_input(690)
    reserve_1 = discrete_input(691)
    reserve_2 = discrete_input(692)
    reserve_3 = discrete_input(693)
    cooling_output = discrete_input(694)
    reserve_5 = discrete_input(695)
    hot_water_block = discrete_input(703)
    heating_block = discrete_input(704)
    utility_block = discrete_input(705)
    sg_ready_1 = discrete_input(706)
    sg_ready_2 = discrete_input(707)
    reserve = discrete_input(714)

    async def async_update(self, *, notify: bool = True) -> None:
        """Refresh supported inputs, excluding addresses rejected by this device."""
        await _update_skipping_unsupported(
            self, super().async_update, "discrete", None, notify=notify
        )
