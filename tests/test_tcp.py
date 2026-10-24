"""End-to-end test over real Modbus TCP against the synthetic WT16."""

from __future__ import annotations

import socket

import pytest

pytest.importorskip("pymodbus")
pytest.importorskip("modbus_connection.tmodbus")

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from pymodbus.server import ModbusTcpServer

from weider_modbus import WeiderWT16

from .simulator import create_device


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def test_simulator_tcp_read_and_write() -> None:
    port = _free_port()
    server = ModbusTcpServer(create_device(), address=("127.0.0.1", port))
    await server.serve_forever(background=True)
    connection = ModbusConnection(ModbusTcpParams(host="127.0.0.1", port=port))
    try:
        device = WeiderWT16(connection.for_unit(1))
        await device.async_update()
        assert device.measurements.hot_water_temperature == 42.5
        assert device.measurements.outdoor_temperature == 8.5
        assert device.measurements.room_temperature == 21.5
        assert device.digital_inputs.compressor is True
        assert device.digital_inputs.remote_fault is False
        await device.async_set_room_target(23.5)
        await device.async_update()
        assert device.settings.room_target_temperature == 23.5
    finally:
        await connection.close()
        await server.shutdown()
