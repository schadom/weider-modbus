"""The top-level WT16 device object."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

from modbus_connection.model import Device, Raw

from .components import DigitalInputs, Measurements, Settings
from .const import MANUFACTURER, MODEL
from .helpers import SgReadyMode, sg_ready_mode
from .rtu import RtuDigitalInputs, RtuMeasurements, RtuSettings

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

# Attribute names of the components, in polling order.
COMPONENTS: Final = ("measurements", "settings", "digital_inputs")

# Measurements that can hold the room temperature, in order of preference.
ROOM_TEMPERATURE_FIELDS: Final = ("room_temperature", "custom_map_room_temperature")


class _WeiderDevice(Device):
    """Behaviour shared by both register maps of the WT16.

    Subclasses create the ``measurements``, ``settings`` and
    ``digital_inputs`` components for their register map.
    """

    manufacturer: Final = MANUFACTURER
    model: Final = MODEL

    measurements: Measurements | RtuMeasurements
    settings: Settings | RtuSettings
    digital_inputs: DigitalInputs | RtuDigitalInputs

    async def async_update(self) -> None:
        """Refresh every component.

        Optional registers the device rejects are dropped on the first poll
        that hits them. Any other ``ModbusError`` propagates, so the caller can
        retry or mark the device unavailable. Listeners fire once every read is
        in, so they see a consistent poll.
        """
        await self.async_ensure_setup()
        for name in COMPONENTS:
            await getattr(self, name).async_update(notify=False)
        for name in COMPONENTS:
            getattr(self, name).notify()

    async def async_set_hot_water_target(self, temperature: float) -> None:
        """Write the hot water target temperature in °C.

        Raises ``ValueError`` if the value is outside the allowed range.
        """
        await self.settings.write("hot_water_target_temperature", temperature)

    async def async_set_room_target(self, temperature: float) -> None:
        """Write the room target temperature in °C.

        Raises ``ValueError`` if the value is outside the allowed range and
        ``AttributeError`` if this device does not provide the register.
        """
        await self.settings.write("room_target_temperature", temperature)

    @property
    def current_room_temperature(self) -> float | None:
        """The room temperature, from whichever register holds it.

        The standard Modbus map provides it at register 12, a custom map at
        register 724. A map answers 0 for the register it does not use, so 0
        means "not provided" here; a real room temperature of exactly 0.0 °C
        does not occur. Returns ``None`` if neither register holds a value, or
        before the first poll.
        """
        for name in ROOM_TEMPERATURE_FIELDS:
            if name in self.measurements.resolved_fields:
                value: float | None = getattr(self.measurements, name)
                if value:
                    return value
        return None

    @property
    def sg_ready_mode(self) -> SgReadyMode | None:
        """The SG Ready operating state, derived from the digital inputs.

        The RS485 map has no SG Ready inputs, so there the state is only
        known while the utility company block is active.
        """
        inputs = self.digital_inputs
        return sg_ready_mode(
            inputs.utility_block,
            getattr(inputs, "sg_ready_1", None),
            getattr(inputs, "sg_ready_2", None),
        )

    async def async_read_raw(self, names: Iterable[str] = COMPONENTS) -> Raw:
        """Return every register this device reads, undecoded, for diagnostics."""
        return await super().async_read_raw(names)


class WeiderWT16TCP(_WeiderDevice):
    """One Weider WT16 heat pump on its Modbus TCP map (Ethernet board).

    The consumer owns the connection and passes a unit. This library only
    reads and writes registers, so it works over any modbus-connection backend.
    """

    measurements: Measurements
    settings: Settings
    digital_inputs: DigitalInputs

    def __init__(self, unit: ModbusUnit) -> None:
        """Create the device and its components. No I/O happens here."""
        super().__init__(unit)
        self.measurements = Measurements(unit)
        self.settings = Settings(unit)
        self.digital_inputs = DigitalInputs(unit)


class WeiderWT16RTU(_WeiderDevice):
    """One Weider WT16 heat pump on its RS485 map (Modbus RTU, terminal X9).

    The RS485 port talks to the controller directly. Its register map differs
    from the Modbus TCP map; values on both maps use the same attribute names.
    The unit can be a serial link or a converter that carries RTU over TCP.
    """

    measurements: RtuMeasurements
    settings: RtuSettings
    digital_inputs: RtuDigitalInputs

    def __init__(self, unit: ModbusUnit) -> None:
        """Create the device and its components. No I/O happens here."""
        super().__init__(unit)
        self.measurements = RtuMeasurements(unit)
        self.settings = RtuSettings(unit)
        self.digital_inputs = RtuDigitalInputs(unit)
