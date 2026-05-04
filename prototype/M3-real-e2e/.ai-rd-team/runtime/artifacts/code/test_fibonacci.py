"""Unit tests for :mod:`fibonacci`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the sibling module is importable when pytest is launched from
# an arbitrary cwd.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from fibonacci import fibonacci  # noqa: E402


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, 0),
        (1, 1),
        (2, 1),
        (3, 2),
        (4, 3),
        (5, 5),
        (6, 8),
        (10, 55),
        (20, 6765),
        (30, 832040),
    ],
)
def test_fibonacci_known_values_returns_expected(n: int, expected: int) -> None:
    assert fibonacci(n) == expected


def test_fibonacci_zero_returns_zero() -> None:
    assert fibonacci(0) == 0


def test_fibonacci_one_returns_one() -> None:
    assert fibonacci(1) == 1


@pytest.mark.parametrize("n", [-1, -2, -10, -100])
def test_fibonacci_negative_input_raises_value_error(n: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        fibonacci(n)


@pytest.mark.parametrize(
    "bad",
    [1.5, "3", None, [1], (1,)],
)
def test_fibonacci_non_int_input_raises_type_error(bad: object) -> None:
    with pytest.raises(TypeError, match="must be an int"):
        fibonacci(bad)  # type: ignore[arg-type]


def test_fibonacci_bool_input_raises_type_error() -> None:
    # ``bool`` is a subclass of ``int`` in Python; we explicitly reject it
    # to avoid ``fibonacci(True) == 1`` surprising callers.
    with pytest.raises(TypeError, match="must be an int"):
        fibonacci(True)  # type: ignore[arg-type]


def test_fibonacci_large_input_matches_recurrence() -> None:
    # Cross-check property: fib(n) == fib(n-1) + fib(n-2)
    n = 50
    assert fibonacci(n) == fibonacci(n - 1) + fibonacci(n - 2)
