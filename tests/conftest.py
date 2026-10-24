"""Shared fixtures for weider-modbus tests."""

from __future__ import annotations

import pytest
from modbus_connection.mock import MockModbusUnit

from weider_modbus import WeiderWT16


@pytest.fixture
def unit(mock_modbus_unit: MockModbusUnit) -> MockModbusUnit:
    """A mock WT16 with a few known register values."""
    mock_modbus_unit.input.update({13: 425, 724: 215, 44: 1234, 60164: [1, 2]})
    mock_modbus_unit.holding.update({1: 450, 723: 220})
    mock_modbus_unit.discrete[679] = True
    return mock_modbus_unit


@pytest.fixture
def device(unit: MockModbusUnit) -> WeiderWT16:
    """A WT16 over the mock unit."""
    return WeiderWT16(unit)
