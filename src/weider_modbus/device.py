"""The top-level WT16 device object."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

from modbus_connection.model import Device, Raw

from .components import DigitalInputs, Measurements, Settings
from .const import MANUFACTURER, MODEL
from .helpers import SgReadyMode, sg_ready_mode

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

# Attribute names of the components, in polling order.
COMPONENTS: Final = ("measurements", "settings", "digital_inputs")


class WeiderWT16(Device):
    """One Weider WT16 heat pump, reached through a ``ModbusUnit``.

    The consumer owns the connection and passes a unit. This library only
    reads and writes registers, so it works over any modbus-connection backend.
    """

    manufacturer: Final = MANUFACTURER
    model: Final = MODEL

    def __init__(self, unit: ModbusUnit) -> None:
        """Create the device and its components. No I/O happens here."""
        super().__init__(unit)
        self.measurements = Measurements(unit)
        self.settings = Settings(unit)
        self.digital_inputs = DigitalInputs(unit)

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
    def sg_ready_mode(self) -> SgReadyMode | None:
        """The SG Ready operating state, derived from the digital inputs."""
        inputs = self.digital_inputs
        return sg_ready_mode(inputs.utility_block, inputs.sg_ready_1, inputs.sg_ready_2)

    async def async_read_raw(self, names: Iterable[str] = COMPONENTS) -> Raw:
        """Return every register this device reads, undecoded, for diagnostics."""
        return await super().async_read_raw(names)
