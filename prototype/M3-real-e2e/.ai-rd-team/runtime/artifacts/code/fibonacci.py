"""Fibonacci sequence utilities.

This module provides an iterative implementation of the Fibonacci function,
following these conventions:
- fib(0) == 0, fib(1) == 1
- Negative inputs raise ValueError
- Iterative algorithm keeps O(n) time and O(1) extra space
"""

from __future__ import annotations


def fibonacci(n: int) -> int:
    """Return the n-th Fibonacci number using an iterative algorithm.

    Args:
        n: A non-negative integer index into the Fibonacci sequence.

    Returns:
        The n-th Fibonacci number, where fib(0) == 0 and fib(1) == 1.

    Raises:
        ValueError: If ``n`` is negative.
        TypeError: If ``n`` is not an ``int`` (booleans excluded).
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"n must be an int, got {type(n).__name__}")
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


__all__ = ["fibonacci"]
