from __future__ import annotations


def fibonacci(n: int) -> int:
    """返回第 n 个斐波那契数。

    定义：fib(0) = 0, fib(1) = 1, fib(k) = fib(k-1) + fib(k-2)。

    Args:
        n: 非负整数索引，要求 n >= 0。

    Returns:
        第 n 个斐波那契数。

    Raises:
        ValueError: 当 n 为负数时抛出。
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")

    if n < 2:
        return n

    prev, curr = 0, 1
    for _ in range(2, n + 1):
        prev, curr = curr, prev + curr
    return curr
