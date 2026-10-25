# weider-modbus

Async Python library for the Modbus TCP interface of Weider heat pumps,
built on [modbus-connection](https://github.com/home-assistant-libs/modbus-connection).

> [!IMPORTANT]
> This library is not affiliated with Weider Wärmepumpen GmbH and is provided
> as-is and without warranty.

The library only reads and writes registers. It takes a `ModbusUnit` and never
opens a connection itself, so it works over any modbus-connection backend
(tmodbus, pymodbus, or the in-memory mock). It is used by the
[Weider Home Assistant integration](https://github.com/schadom/hacs_weider).

## Supported controllers

| Controller | Modbus | Class |
| --- | --- | --- |
| WeiTronic WT16 | Yes | `WeiderWT16` |
| WeiTronic WT08 | No | Not supported |

Only the WT16 controller has a Modbus interface. The Modbus layout is specific
to the controller model, so each supported model has its own class, and
`device.model` returns the model name.

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

from weider_modbus import WeiderWT16, plausible_temperature


async def main() -> None:
    connection = ModbusConnection(ModbusTcpParams(host="192.168.1.50", port=502))
    try:
        device = WeiderWT16(connection.for_unit(1))
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

### Components

| Attribute | Modbus space | Content |
| --- | --- | --- |
| `device.measurements` | Input registers (FC04) | Temperatures, volume flow, runtimes, mixer position, active error text |
| `device.settings` | Holding registers (FC03/FC16) | Hot water and room target temperatures |
| `device.digital_inputs` | Discrete inputs (FC02) | Compressor, pumps, valves, blocks, SG Ready inputs |

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
(hot water 15–55 °C, room 15–35 °C), before anything is written.

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
