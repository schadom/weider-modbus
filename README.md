# weider-modbus

Async Python library for the Modbus interfaces (TCP and RTU) of Weider heat
pumps, built on [modbus-connection](https://github.com/home-assistant-libs/modbus-connection).

> [!IMPORTANT]
> This library is not affiliated with Weider Wärmepumpen GmbH and is provided
> as-is and without warranty.

The library only reads and writes registers. It takes a `ModbusUnit` and never
opens a connection itself, so it works over any modbus-connection backend
(tmodbus, pymodbus, or the in-memory mock). It is used by the
[Weider Home Assistant integration](https://github.com/schadom/hacs_weider).

## Supported controllers

| Controller | RS232 | RS485 | Ethernet | Modbus RTU | Modbus TCP | Class |
| --- | --- | --- | --- | --- | --- | --- |
| WeiTronic WT16 | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | `WeiderWT16TCP` (Ethernet),<br>`WeiderWT16RTU` (RS485) |
| WeiTronic WT08 | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes | ❌ No | Not yet supported |

The library reads the controller as a Modbus slave, which only the WT16
supports. The Modbus layout is specific to the controller model and to the
interface, so each has its own class, and `device.model` returns the model name.

`WeiderWT16TCP` was called `WeiderWT16` before version 0.2.0. The old name
still works but is deprecated and will be removed in version 1.0.

## Register maps

The WT16 has two Modbus interfaces with different register maps:

| | Modbus TCP | Modbus RTU |
| --- | --- | --- |
| Class | `WeiderWT16TCP` | `WeiderWT16RTU` |
| Connection | Ethernet board (RJ45) | RS485 port X9 ("Modbus 1") |
| Reads | Input registers (FC04), holding registers (FC03), discrete inputs (FC02) | Holding registers only (FC03) |
| Target writes | FC16 | FC06 |

Values on both maps use the same attribute names, units and scaling, so a
consumer reads either device the same way. Several values sit at other
addresses: for example the hot water temperature is input register 13 on TCP
and holding register 2 on RTU, the room temperature input register 12 on TCP and
holding register 724 on RTU.

Some values exist on only one map. A value a map does not provide is not an
attribute of that device's components.

- **TCP only:** refrigerant circuit temperatures (superheat, evaporation,
  condensation, evaporator, suction gas, hot gas, defrost), flow target and
  mixer temperature, volume flow, flow switches, 4-way valve, SG Ready inputs,
  last pump runtime (32-bit) and the active error text.
- **RTU only:** hot water hysteresis, heating limit temperature, average outdoor
  temperature, summer/winter mode, flow target and flow temperature of heating
  circuit 1, mixer 2 position, operating hours, last heating runtime, heat meter
  energy (kWh), the active error number and the manual SG Ready mode.

On RTU, the runtimes and counters are 16-bit values. Only the two target
temperatures are writable on either map.

The RS485 port connects directly to the controller, so it is not affected by
the Ethernet board's network resets. It must be enabled on the controller as a
Modbus slave in RTU mode (Modbus 1); ask Weider for the required settings.

## Installation

```bash
pip install weider-modbus
```

The library depends only on the backend-neutral `modbus-connection`
interface. To open a connection yourself, also install a backend:

```bash
pip install "modbus-connection[tmodbus]"
```

## Usage

```python
import asyncio

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

from weider_modbus import WeiderWT16TCP, plausible_temperature


async def main() -> None:
    connection = ModbusConnection(ModbusTcpParams(host="192.168.1.50", port=502))
    try:
        device = WeiderWT16TCP(connection.for_unit(1))
        await device.async_update()

        print("Hot water:", device.measurements.hot_water_temperature)
        print("Room:", device.current_room_temperature)
        outdoor = plausible_temperature(device.measurements.outdoor_temperature)
        print("Outdoor:", outdoor)
        print("Compressor running:", device.digital_inputs.compressor)
        print("SG Ready mode:", device.sg_ready_mode)

        await device.async_set_hot_water_target(47.5)
    finally:
        await connection.close()


asyncio.run(main())
```

Over RS485, open a serial connection and use `WeiderWT16RTU`. The serial
settings must match the controller's Modbus 1 settings:

```python
from modbus_connection import ModbusSerialParams

from weider_modbus import WeiderWT16RTU

connection = ModbusConnection(
    ModbusSerialParams(
        device="/dev/serial/by-id/usb-1a86_USB_Single_Serial_0123456789-if00",
        baudrate=19200,
        parity="N",
        stopbits=2,
    )
)
device = WeiderWT16RTU(connection.for_unit(1))
```

### Components

| Attribute | Modbus space (TCP / RTU) | Content |
| --- | --- | --- |
| `device.measurements` | Input registers (FC04) / holding registers (FC03) | Temperatures, volume flow, runtimes, counters, mixer position, active error |
| `device.settings` | Holding registers (FC03/FC16) / holding registers (FC03/FC06) | Target temperatures; on RTU also hysteresis and heating limit (read-only) |
| `device.digital_inputs` | Discrete inputs (FC02) / 0/1 holding registers (FC03) | Compressor, pumps, valves, blocks, SG Ready inputs |

A value reads as `None` until the first successful poll, or if the device
does not provide the register.

### Optional registers

The room temperature is read from input register 12 (`BET.T.A.1`, the measured
sensor value) of the standard Modbus map. Some heat pumps have a custom Modbus
map that Weider configures on request. Such a map answers 0 at register 12 and
provides the room temperature at register 724 instead
(`measurements.custom_map_room_temperature`). Use
`device.current_room_temperature` for the value to display: register 12 if it is
non-zero, otherwise register 724 if it is non-zero, otherwise `None`.

Some firmware versions do not provide every register. The room temperature,
room target, mixer position, runtimes, active error text and any digital input
are optional. If the device rejects one of them with an illegal data address,
the library drops that register on the first poll and stops reading it. Any
other register error still raises, so real problems are not hidden.

### Errors

`async_update()` raises a `modbus_connection.ModbusError` subclass (or
`TimeoutError` / `OSError` from the transport) when a poll fails. The shared
connection reopens on the next request, so the caller can simply retry.

The target setters raise `ValueError` for a value outside the allowed range
(hot water 15–55 °C, room 5–35 °C), before anything is written.

### Writing targets

The controller stores the target temperatures in flash memory. Flash memory
tolerates only a limited number of write cycles (typically around 100,000), and
exceeding it can damage the controller. Write a target only when it actually
changes, and do not write targets on a short schedule or from a fast control
loop.

### Helpers

- `plausible_temperature(value)` returns `None` for the placeholder values the
  device reports for an unconnected sensor (outside −45 to 150 °C).
- `clean_error_text(value)` strips the padding from the active error text and
  returns `None` when there is no error.
- `sg_ready_mode(...)` and `device.sg_ready_mode` derive the SG Ready operating
  state (BZ1–BZ4) from the digital inputs.

## Hardware verification

The register addresses, the signed 0.1 °C temperature format and the
multi-register word order come from the existing integration. Confirm them
against your WT16 documentation, especially for negative temperatures. The
test simulator checks the software against this map, not the map against a
real heat pump.

The RTU map has been checked on a WT16 over a USB-RS485 adapter (19200 baud,
8N2), including reads of adjacent registers in one request. A temperature
sensor that is not connected reads -99.9 °C on RTU; `plausible_temperature`
treats it as unknown. When there is no active error, the error number is -1.

## Development

Requires Python 3.13 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

To run the synthetic WT16 on port 5020 for manual testing:

```bash
uv run python -m tests.simulator
```

## Releasing

Releases are published to PyPI from GitHub Actions with
[trusted publishing](https://docs.pypi.org/trusted-publishers/).

1. Set the new `version` in `pyproject.toml` and merge it to `main`.
2. Create a GitHub release with a tag equal to that version (for example
   `0.1.0`).
3. The `Publish` workflow builds the package and uploads it to PyPI.

A version number can be published only once.

## License

MIT. See [LICENSE](LICENSE).
