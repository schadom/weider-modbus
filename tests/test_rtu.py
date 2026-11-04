"""Tests for the RS485 (Modbus RTU) register map."""

from __future__ import annotations

import pytest
from modbus_connection.exceptions import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit, WriteEvent

from weider_modbus import (
    DigitalInputs,
    Measurements,
    RtuDigitalInputs,
    RtuMeasurements,
    RtuSettings,
    Settings,
    SgReadyMode,
    WeiderWT16RTU,
)


@pytest.fixture
def rtu_unit(mock_modbus_unit: MockModbusUnit) -> MockModbusUnit:
    """A mock WT16 RS485 port with a few known register values."""
    mock_modbus_unit.holding.update(
        {
            1: 480,
            2: 576,
            15: 65516,  # -2.0 °C
            26: 271,
            454: 1,
            724: 231,
            1137: 40000,
            1195: 35000,
            4079: 65535,  # -1: no active error
            679: 1,
            685: 0,
            723: 230,
        }
    )
    return mock_modbus_unit


@pytest.fixture
def rtu_device(rtu_unit: MockModbusUnit) -> WeiderWT16RTU:
    """A WT16 on its RS485 map over the mock unit."""
    return WeiderWT16RTU(rtu_unit)


async def test_reads_holding_registers_only(
    rtu_unit: MockModbusUnit, rtu_device: WeiderWT16RTU
) -> None:
    await rtu_device.async_update()
    assert {event.register_type for event in rtu_unit.read_events} == {"holding"}
    assert rtu_device.measurements.hot_water_temperature == 57.6
    assert rtu_device.measurements.outdoor_temperature == pytest.approx(-2.0)
    assert rtu_device.measurements.return_temperature == pytest.approx(27.1)
    assert rtu_device.measurements.winter_mode is True
    assert rtu_device.settings.hot_water_target_temperature == 48
    assert rtu_device.settings.room_target_temperature == 23


async def test_no_active_error_reads_minus_one(rtu_device: WeiderWT16RTU) -> None:
    await rtu_device.async_update()
    assert rtu_device.measurements.active_error_code == -1


async def test_counters_are_unsigned(rtu_device: WeiderWT16RTU) -> None:
    await rtu_device.async_update()
    assert rtu_device.measurements.operating_hours == 40000
    assert rtu_device.measurements.heat_energy == 35000


async def test_states_from_holding_registers(rtu_device: WeiderWT16RTU) -> None:
    await rtu_device.async_update()
    assert rtu_device.digital_inputs.compressor is True
    assert rtu_device.digital_inputs.hot_water_pump is False


async def test_registers_read_in_blocks(
    rtu_unit: MockModbusUnit, rtu_device: WeiderWT16RTU
) -> None:
    await rtu_device.async_update()
    blocks = sorted((e.address, e.count) for e in rtu_unit.read_events)
    assert blocks == [
        (1, 1), (2, 1), (4, 1), (15, 2), (18, 3), (25, 4),
        (451, 1), (452, 1), (454, 1), (679, 4), (685, 2), (691, 5), (703, 3),
        (723, 1), (724, 1), (726, 2), (736, 1), (767, 1), (1137, 2), (1148, 2),
        (1195, 1), (4079, 1), (4086, 1),
    ]  # fmt: skip
    assert all(event.count <= 50 for event in rtu_unit.read_events)


@pytest.mark.parametrize(
    ("method", "address", "value", "raw"),
    [
        ("async_set_hot_water_target", 1, 47.5, 475),
        ("async_set_room_target", 723, 21.5, 215),
    ],
)
async def test_target_writes_use_fc06(
    rtu_unit: MockModbusUnit,
    rtu_device: WeiderWT16RTU,
    method: str,
    address: int,
    value: float,
    raw: int,
) -> None:
    events: list[WriteEvent] = []
    rtu_unit.on_write(events.append)
    await getattr(rtu_device, method)(value)
    assert events == [WriteEvent("holding", address, [raw], 6)]


async def test_target_out_of_range_is_not_written(
    rtu_unit: MockModbusUnit, rtu_device: WeiderWT16RTU
) -> None:
    events: list[WriteEvent] = []
    rtu_unit.on_write(events.append)
    with pytest.raises(ValueError):
        await rtu_device.async_set_hot_water_target(60)
    assert events == []


def test_read_only_settings_are_not_writable() -> None:
    for name in ("hot_water_hysteresis", "heating_limit_temperature"):
        assert not getattr(RtuSettings, name).writable


async def test_current_room_temperature(rtu_device: WeiderWT16RTU) -> None:
    assert rtu_device.current_room_temperature is None
    await rtu_device.async_update()
    assert rtu_device.current_room_temperature == pytest.approx(23.1)


@pytest.mark.parametrize(
    ("utility_block", "expected"),
    [(1, SgReadyMode.UTILITY_BLOCK), (0, None)],
)
async def test_sg_ready_mode_without_sg_ready_inputs(
    rtu_unit: MockModbusUnit,
    rtu_device: WeiderWT16RTU,
    utility_block: int,
    expected: SgReadyMode | None,
) -> None:
    rtu_unit.holding[705] = utility_block
    await rtu_device.async_update()
    assert rtu_device.sg_ready_mode is expected


async def test_unsupported_optional_register_is_skipped(
    rtu_unit: MockModbusUnit, rtu_device: WeiderWT16RTU
) -> None:
    rtu_unit.fail_read(1195, IllegalDataAddressError(), register_type="holding")
    await rtu_device.async_update()
    assert rtu_device.measurements.heat_energy is None
    assert "heat_energy" not in rtu_device.measurements.resolved_fields
    assert rtu_device.measurements.hot_water_temperature == 57.6


async def test_unsupported_required_register_still_fails(
    rtu_unit: MockModbusUnit, rtu_device: WeiderWT16RTU
) -> None:
    rtu_unit.fail_read(2, IllegalDataAddressError(), register_type="holding")
    with pytest.raises(IllegalDataAddressError):
        await rtu_device.async_update()


def test_identity(rtu_device: WeiderWT16RTU) -> None:
    assert (rtu_device.manufacturer, rtu_device.model) == ("Weider", "WT16")


@pytest.mark.parametrize(
    ("tcp", "rtu"),
    [
        (Measurements, RtuMeasurements),
        (Settings, RtuSettings),
        (DigitalInputs, RtuDigitalInputs),
    ],
)
def test_shared_fields_match_between_maps(
    mock_modbus_unit: MockModbusUnit, tcp: type, rtu: type
) -> None:
    """A value on both maps keeps its name, unit and scaling."""
    tcp_fields = tcp(mock_modbus_unit).resolved_fields
    rtu_fields = rtu(mock_modbus_unit).resolved_fields
    shared = set(tcp_fields) & set(rtu_fields)
    assert shared
    for name in shared:
        tcp_field, rtu_field = tcp_fields[name].field, rtu_fields[name].field
        unit = getattr(tcp_field, "unit", None), getattr(rtu_field, "unit", None)
        assert unit[0] == unit[1], name
        # A bit field has no scale; a 0/1 register has a scale of 1.
        scale = getattr(tcp_field, "scale", 1.0), getattr(rtu_field, "scale", 1.0)
        assert scale[0] == scale[1], name
