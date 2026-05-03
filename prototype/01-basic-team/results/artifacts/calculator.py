"""简易四则运算计算器。

根据 design-note.md 中的接口定义实现。
"""


def calc(op: str, a: float, b: float) -> float:
    """执行基础四则运算并返回结果。

    Args:
        op: 运算符，取值 "+"、"-"、"*"、"/"。
        a: 左操作数。
        b: 右操作数。

    Returns:
        运算结果。

    Raises:
        ZeroDivisionError: 当 op == "/" 且 b == 0 时抛出。
        ValueError: 当 op 不在支持的运算符集合中时抛出。
    """
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ZeroDivisionError("division by zero")
        return a / b
    raise ValueError(f"unsupported operator: {op}")
