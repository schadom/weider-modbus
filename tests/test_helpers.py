"""Tests for value interpretation helpers."""

from __future__ import annotations

import pytest

from weider_modbus import (
    SgReadyMode,
    clean_error_text,
    plausible_temperature,
    sg_ready_mode,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (21.5, 21.5),
        (150.0, 150.0),
        (150.1, None),
        (3276.7, None),
        (-45.0, -45.0),
        (-45.1, None),
        (None, None),
    ],
)
def test_plausible_temperature(value: float | None, expected: float | None) -> None:
    assert plausible_temperature(value) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", None),
        (" " * 32, None),
        ("\x00" * 32, None),
        ("E12 HD", "E12 HD"),
        ("  E12   HD  ", "E12 HD"),
        ("\x00\x00E05", "E05"),
        (None, None),
    ],
)
def test_clean_error_text(raw: str | None, expected: str | None) -> None:
    assert clean_error_text(raw) == expected


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        ((True, None, None), SgReadyMode.UTILITY_BLOCK),
        ((None, False, False), SgReadyMode.NORMAL),
        ((False, None, True), None),
        ((False, True, None), None),
    ],
)
def test_sg_ready_mode_with_missing_inputs(
    inputs: tuple[bool | None, bool | None, bool | None], expected: SgReadyMode | None
) -> None:
    assert sg_ready_mode(*inputs) == expected
