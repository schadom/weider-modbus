"""Tests for reading and writing the WT16 register map."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from modbus_connection import ModbusError
from modbus_connection.exceptions import IllegalDataAddressError, IllegalDataValueError
from modbus_connection.mock import MockModbusUnit, WriteEvent

from weider_modbus import SgReadyMode, WeiderWT16


async def test_reads_and_fc16_writes(unit: MockModbusUnit, device: WeiderWT16) -> None:
    await device.async_update()
    assert device.measurements.hot_water_temperature == 42.5
    assert device.measurements.room_temperature == 21.5
    assert device.measurements.volume_flow == 1.234
    assert device.measurements.last_pump_runtime == 65538
    assert device.digital_inputs.compressor is True
    assert device.settings.hot_water_target_temperature == 45
    assert all(event.count <= 50 for event in unit.read_events)
    assert not any(
        event.address <= 725 < event.address + event.count
        for event in unit.read_events
        if event.register_type == "input"
    )
    assert {event.register_type for event in unit.read_events} == {
        "input",
        "holding",
        "discrete",
    }
    events: list[WriteEvent] = []
    unit.on_write(events.append)
    await device.async_set_hot_water_target(47.5)
    assert events == [WriteEvent("holding", 1, [475], 16)]
    await device.async_update()
    assert device.settings.hot_water_target_temperature == 47.5


async def test_room_target_write(unit: MockModbusUnit, device: WeiderWT16) -> None:
    events: list[WriteEvent] = []
    unit.on_write(events.append)
    await device.async_set_room_target(23.5)
    assert events == [WriteEvent("holding", 723, [235], 16)]


@pytest.mark.parametrize(
    ("method", "value"),
    [
        ("async_set_hot_water_target", 14.5),
        ("async_set_hot_water_target", 55.5),
        ("async_set_room_target", 14.5),
        ("async_set_room_target", 35.5),
    ],
)
async def test_target_out_of_range_is_not_written(
    unit: MockModbusUnit, device: WeiderWT16, method: str, value: float
) -> None:
    events: list[WriteEvent] = []
    unit.on_write(events.append)
    with pytest.raises(ValueError):
        await getattr(device, method)(value)
    assert events == []


@pytest.mark.parametrize(
    ("method", "value"),
    [
        ("async_set_hot_water_target", 15),
        ("async_set_hot_water_target", 55),
        ("async_set_room_target", 35),
    ],
)
async def test_target_range_is_inclusive(
    device: WeiderWT16, method: str, value: float
) -> None:
    await getattr(device, method)(value)


@pytest.mark.parametrize(
    ("raw", "expected"), [(85, 8.5), (0, 0.0), (65516, -2.0), (65336, -20.0)]
)
async def test_temperatures_below_zero(
    unit: MockModbusUnit, device: WeiderWT16, raw: int, expected: float
) -> None:
    unit.input.update({15: raw, 27: raw, 31: raw})
    await device.async_update()
    assert device.measurements.outdoor_temperature == pytest.approx(expected)
    assert device.measurements.source_inlet_temperature == pytest.approx(expected)
    assert device.measurements.evaporation_temperature == pytest.approx(expected)


async def test_registers_read_in_blocks(
    unit: MockModbusUnit, device: WeiderWT16
) -> None:
    await device.async_update()
    blocks = {
        kind: sorted(
            (e.address, e.count) for e in unit.read_events if e.register_type == kind
        )
        for kind in ("input", "holding", "discrete")
    }
    assert blocks["discrete"] == [
        (45, 1),
        (69, 1),
        (679, 4),
        (685, 2),
        (690, 6),
        (703, 5),
        (714, 1),
    ]
    assert blocks["input"] == [
        (13, 9), (25, 5), (31, 1), (33, 1), (35, 3), (44, 1), (724, 1), (736, 1),
        (60164, 2), (60168, 2), (63000, 16),
    ]  # fmt: skip
    assert blocks["holding"] == [(1, 1), (723, 1)]


@pytest.mark.parametrize("previously_supported", [False, True])
async def test_unsupported_digital_inputs(
    unit: MockModbusUnit, device: WeiderWT16, previously_supported: bool
) -> None:
    unit.discrete[690] = True
    if previously_supported:
        await device.async_update()
        assert device.digital_inputs.four_way_valve is True
    read = unit.read_discrete_inputs
    rejected = []

    async def read_supported(address: int, count: int) -> list[bool]:
        if any(address <= missing < address + count for missing in (690, 704)):
            rejected.append(address)
            raise IllegalDataAddressError()
        return await read(address, count)

    with patch.object(unit, "read_discrete_inputs", side_effect=read_supported):
        await device.async_update()
        assert device.digital_inputs.four_way_valve is None
        assert device.digital_inputs.heating_block is None
        assert device.digital_inputs.compressor is True
        assert device.digital_inputs.reserve_1 is False
        assert device.digital_inputs.utility_block is False
        first_rejections = list(rejected)
        unit.discrete[679] = False
        await device.async_update()
        assert device.digital_inputs.compressor is False
        assert rejected == first_rejections
    # A fresh device starts from the full declared layout again.
    assert WeiderWT16(unit).digital_inputs.four_way_valve is None
    assert "four_way_valve" in WeiderWT16(unit).digital_inputs.resolved_fields


async def test_unsupported_input_inside_block(
    unit: MockModbusUnit, device: WeiderWT16
) -> None:
    unit.discrete.update({691: True, 695: True})
    unit.fail_read(690, IllegalDataAddressError(), register_type="discrete")
    await device.async_update()
    assert device.digital_inputs.four_way_valve is None
    assert device.digital_inputs.reserve_1 is True
    assert device.digital_inputs.reserve_5 is True
    unit.read_events.clear()
    await device.async_update()
    discrete = [
        (e.address, e.count) for e in unit.read_events if e.register_type == "discrete"
    ]
    assert (691, 5) in discrete
    assert not any(address <= 690 < address + count for address, count in discrete)


async def test_unsupported_core_register_inside_block_still_fails(
    unit: MockModbusUnit, device: WeiderWT16
) -> None:
    unit.fail_read(17, IllegalDataAddressError(), register_type="input")
    with pytest.raises(IllegalDataAddressError):
        await device.async_update()
    assert "mixer_temperature" in device.measurements.resolved_fields


@pytest.mark.parametrize(
    "error",
    [ModbusError("offline"), TimeoutError("timed out"), IllegalDataValueError()],
)
async def test_digital_input_communication_errors_propagate(
    unit: MockModbusUnit, device: WeiderWT16, error: Exception
) -> None:
    with (
        patch.object(unit, "read_discrete_inputs", side_effect=error),
        pytest.raises(type(error)),
    ):
        await device.async_update()
    assert len(device.digital_inputs.resolved_fields) == 20


@pytest.mark.parametrize(
    ("field", "address"),
    [
        ("room_temperature", 724),
        ("mixer_position", 736),
        ("last_pump_runtime", 60164),
        ("last_hot_water_runtime", 60168),
        ("active_error", 63000),
    ],
)
async def test_unsupported_optional_measurement(
    unit: MockModbusUnit, device: WeiderWT16, field: str, address: int
) -> None:
    unit.fail_read(address, IllegalDataAddressError(), register_type="input")
    await device.async_update()
    assert getattr(device.measurements, field) is None
    assert field not in device.measurements.resolved_fields
    assert device.measurements.hot_water_temperature == 42.5
    rejected_reads = len([e for e in unit.read_events if e.address == address])
    await device.async_update()
    assert len([e for e in unit.read_events if e.address == address]) == rejected_reads
    assert field in WeiderWT16(unit).measurements.resolved_fields


async def test_unsupported_core_measurement_still_fails(
    unit: MockModbusUnit, device: WeiderWT16
) -> None:
    unit.fail_read(15, IllegalDataAddressError(), register_type="input")
    with pytest.raises(IllegalDataAddressError):
        await device.async_update()
    assert "outdoor_temperature" in device.measurements.resolved_fields


async def test_unsupported_room_target(
    unit: MockModbusUnit, device: WeiderWT16
) -> None:
    unit.fail_read(723, IllegalDataAddressError(), register_type="holding")
    await device.async_update()
    assert device.settings.room_target_temperature is None
    assert "room_target_temperature" not in device.settings.resolved_fields
    assert device.settings.hot_water_target_temperature == 45
    with pytest.raises(AttributeError):
        await device.async_set_room_target(22)


async def test_listeners_fire_once_after_full_poll(device: WeiderWT16) -> None:
    seen: list[tuple[float | None, bool | None]] = []

    def listener() -> None:
        # Every component is already fresh when the first listener runs.
        seen.append(
            (
                device.measurements.hot_water_temperature,
                device.digital_inputs.compressor,
            )
        )

    device.measurements.add_update_listener(listener)
    device.digital_inputs.add_update_listener(listener)
    await device.async_update()
    assert seen == [(42.5, True), (42.5, True)]


@pytest.mark.parametrize(
    ("utility_block", "sg_ready_1", "sg_ready_2", "expected"),
    [
        (True, True, True, SgReadyMode.UTILITY_BLOCK),
        (False, False, False, SgReadyMode.NORMAL),
        (False, True, True, SgReadyMode.NORMAL),
        (False, False, True, SgReadyMode.INCREASED),
        (False, True, False, SgReadyMode.START),
    ],
)
async def test_sg_ready_mode(
    unit: MockModbusUnit,
    device: WeiderWT16,
    utility_block: bool,
    sg_ready_1: bool,
    sg_ready_2: bool,
    expected: SgReadyMode,
) -> None:
    unit.discrete.update({705: utility_block, 706: sg_ready_1, 707: sg_ready_2})
    await device.async_update()
    assert device.sg_ready_mode is expected


async def test_sg_ready_mode_before_first_poll(device: WeiderWT16) -> None:
    assert device.sg_ready_mode is None


async def test_read_raw(device: WeiderWT16) -> None:
    raw = await device.async_read_raw()
    assert raw["input"][13] == 425
    assert raw["holding"][1] == 450
    assert raw["discrete"][679] is True


def test_identity(device: WeiderWT16) -> None:
    assert (device.manufacturer, device.model) == ("Weider", "WT16")
