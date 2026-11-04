"""Components for the RS485 port (Modbus RTU) of the Weider WT16.

The RS485 port (terminal X9, "Modbus 1") talks to the controller directly,
without the Ethernet board. It uses its own register map: every value is a
holding register, read with function code 03 and written with function code
06. Several values sit at other addresses than on the Modbus TCP map, and
some exist on only one of the two maps.

Values that exist on both maps use the same attribute names as the TCP
components, so a consumer can read either device the same way.
"""

from __future__ import annotations

from typing import ClassVar

from modbus_connection.model import Component, boolean, gauge, integer

from .components import (
    _target_temperature,
    _temperature,
    _update_skipping_unsupported,
)
from .const import (
    HOT_WATER_TARGET_MAX,
    HOT_WATER_TARGET_MIN,
    ROOM_TARGET_MAX,
    ROOM_TARGET_MIN,
)

__all__ = ["RtuDigitalInputs", "RtuMeasurements", "RtuSettings"]


class RtuMeasurements(Component):
    """Read-only WT16 values on the RS485 map (holding registers, FC03)."""

    register_space = "holding"
    # max_gap = 1 merges directly adjacent registers only, never across a gap.
    max_gap = 1
    max_span = 50

    hot_water_temperature = _temperature(2)
    outdoor_temperature = _temperature(15)
    buffer_temperature = _temperature(16)
    reserve_temperature_1 = _temperature(18)
    reserve_temperature_2 = _temperature(19)
    reserve_temperature_3 = _temperature(20)
    flow_temperature = _temperature(25)
    source_inlet_temperature = _temperature(27)
    source_outlet_temperature = _temperature(28)
    return_temperature = _temperature(62)
    average_outdoor_temperature = _temperature(452)
    # 0 is summer operation, 1 is winter operation.
    winter_mode = boolean(454)
    # Room temperature of heating circuit 1, measured by the room sensor.
    room_temperature = _temperature(724)
    circuit_1_flow_target_temperature = _temperature(726)
    circuit_1_flow_temperature = _temperature(727)
    mixer_position = integer(736, signed=False)
    mixer_2_position = integer(767, signed=False)
    operating_hours = integer(1137, signed=False, unit="h")
    heating_hours = integer(1138, signed=False, unit="h")
    last_heating_runtime = integer(1148, signed=False, unit="min")
    last_hot_water_runtime = integer(1149, signed=False, unit="min")
    heat_energy = integer(1195, signed=False, unit="kWh")
    # Number of the active error. The controller reports -1 if there is none.
    active_error_code = integer(4079)
    # SG Ready operating state set manually on the controller (0 to 3).
    sg_ready_manual_mode = integer(4086, signed=False)

    # Registers that only the core temperatures are required for.
    REQUIRED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"hot_water_temperature", "outdoor_temperature"}
    )

    async def async_update(self, *, notify: bool = True) -> None:
        """Refresh measurements, skipping optional registers this device rejects."""
        optional = frozenset(self.resolved_fields) - self.REQUIRED_FIELDS
        await _update_skipping_unsupported(
            self, super().async_update, "holding", optional, notify=notify
        )


class RtuSettings(Component):
    """WT16 settings on the RS485 map (holding registers, FC03/FC06).

    Only the two target temperatures are writable. The hysteresis and the
    heating limit are read-only here, because every write goes to the
    controller's flash memory.
    """

    register_space = "holding"
    max_gap = 0
    max_span = 50

    hot_water_target_temperature = _target_temperature(
        1, HOT_WATER_TARGET_MIN, HOT_WATER_TARGET_MAX, force_fc16=False
    )
    hot_water_hysteresis = gauge(4, 0.1, signed=False, unit="°C")
    heating_limit_temperature = _temperature(451)
    room_target_temperature = _target_temperature(
        723, ROOM_TARGET_MIN, ROOM_TARGET_MAX, force_fc16=False
    )

    OPTIONAL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "hot_water_hysteresis",
            "heating_limit_temperature",
            "room_target_temperature",
        }
    )

    async def async_update(self, *, notify: bool = True) -> None:
        """Refresh settings, skipping optional registers this device rejects."""
        await _update_skipping_unsupported(
            self, super().async_update, "holding", self.OPTIONAL_FIELDS, notify=notify
        )


class RtuDigitalInputs(Component):
    """WT16 on/off states on the RS485 map (0/1 holding registers, FC03)."""

    register_space = "holding"
    # max_gap = 1 merges directly adjacent registers only, never across a gap.
    max_gap = 1
    max_span = 50

    compressor = boolean(679)
    heating_pump = boolean(680)
    source_pump = boolean(681)
    mixer_pump = boolean(682)
    hot_water_pump = boolean(685)
    remote_fault = boolean(686)
    reserve_1 = boolean(691)
    reserve_2 = boolean(692)
    reserve_3 = boolean(693)
    cooling_output = boolean(694)
    reserve_5 = boolean(695)
    hot_water_block = boolean(703)
    heating_block = boolean(704)
    utility_block = boolean(705)

    async def async_update(self, *, notify: bool = True) -> None:
        """Refresh supported states, excluding addresses rejected by this device."""
        await _update_skipping_unsupported(
            self, super().async_update, "holding", None, notify=notify
        )
