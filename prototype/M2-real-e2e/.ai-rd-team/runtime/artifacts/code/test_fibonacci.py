from __future__ import annotations

import pytest

from fibonacci import fibonacci


@pytest.mark.parametrize(
    "n,expected",
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


def test_fibonacci_negative_raises_value_error() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        fibonacci(-1)


def test_fibonacci_large_negative_raises_value_error() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        fibonacci(-100)


def test_fibonacci_large_n_is_consistent() -> None:
    # fib(50) 已知值，验证迭代算法对较大 n 依然正确
    assert fibonacci(50) == 12586269025
