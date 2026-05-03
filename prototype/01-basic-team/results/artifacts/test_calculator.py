"""calculator.calc 的 pytest 测试用例。

覆盖：
- +、-、*、/ 四则运算各至少 2 个正向用例
- 浮点数运算
- 除零异常（ZeroDivisionError）
- 未知运算符异常（ValueError）
"""

import pytest

from calculator import calc


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2, 3),
        (-5, 5, 0),
        (0, 0, 0),
    ],
)
def test_add(a, b, expected):
    assert calc("+", a, b) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (5, 3, 2),
        (0, 7, -7),
        (-2, -3, 1),
    ],
)
def test_sub(a, b, expected):
    assert calc("-", a, b) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (2, 3, 6),
        (-4, 5, -20),
        (0, 100, 0),
    ],
)
def test_mul(a, b, expected):
    assert calc("*", a, b) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (10, 2, 5),
        (9, 3, 3),
        (-8, 4, -2),
    ],
)
def test_div(a, b, expected):
    assert calc("/", a, b) == expected


@pytest.mark.parametrize(
    "op, a, b, expected",
    [
        ("+", 0.1, 0.2, 0.3),
        ("-", 1.5, 0.5, 1.0),
        ("*", 2.5, 4.0, 10.0),
        ("/", 1.0, 4.0, 0.25),
    ],
)
def test_float_operations(op, a, b, expected):
    result = calc(op, a, b)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("a", [1, 0, -5, 3.14])
def test_division_by_zero_raises(a):
    with pytest.raises(ZeroDivisionError, match="division by zero"):
        calc("/", a, 0)


@pytest.mark.parametrize("op", ["%", "^", "**", "", "add", "//"])
def test_unsupported_operator_raises(op):
    with pytest.raises(ValueError, match="unsupported operator"):
        calc(op, 1, 2)
