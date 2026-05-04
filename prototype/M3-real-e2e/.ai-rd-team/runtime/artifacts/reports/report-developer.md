# Developer Report — M3 E2E Fibonacci

- 角色：developer（林）
- 任务：实现 `fibonacci(n: int) -> int`（迭代版）并编写 pytest 测试
- 运行档位：lite
- 时间：2026-05-04 13:19 UTC

## 实现思路

- 位置：`artifacts/code/fibonacci.py`
- 算法：迭代双变量滚动，时间 `O(n)`，空间 `O(1)`。
- 契约：
  - `fib(0) == 0`，`fib(1) == 1`
  - `n < 0` 抛 `ValueError("n must be non-negative, got ...")`
  - 非 `int`（含 `bool`）抛 `TypeError`，避免 `fibonacci(True)` 被静默当作 `1`
- 风格：`from __future__ import annotations`、类型注解、具体异常，符合 `python-best-practices` Skill。

```python
def fibonacci(n: int) -> int:
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(...)
    if n < 0:
        raise ValueError(...)
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```

## 测试覆盖

- 位置：`artifacts/code/test_fibonacci.py`
- 用 `@pytest.mark.parametrize` 组织用例，AAA 结构，命名 `test_<对象>_<场景>_<期望>`。
- 覆盖维度：
  1. 已知值：`n ∈ {0,1,2,3,4,5,6,10,20,30}`
  2. 边界：`fib(0)=0`、`fib(1)=1` 单独断言
  3. 负数异常：`n ∈ {-1,-2,-10,-100}` → `ValueError`，`match="non-negative"`
  4. 类型异常：`1.5 / "3" / None / list / tuple` → `TypeError`
  5. bool 被拒绝（避免 `True` 走 `int` 路径）
  6. 递推性质：`fib(50) == fib(49) + fib(48)` 交叉验证

## 验证结果

```text
platform linux -- Python 3.11.6, pytest-9.0.3
collected 23 items
...
============================== 23 passed in 0.09s ==============================
```

全部 23 个用例通过。pytest 额外发出的 `coverage no-data-collected` 警告来自仓库根 `pyproject.toml` 的 `--cov=src/ai_rd_team` 配置（针对主工程），与本次产物目录无关，不影响用例结果。

## 产物

- `artifacts/code/fibonacci.py`
- `artifacts/code/test_fibonacci.py`
- `artifacts/reports/report-developer.md`（本文件）

## 后续建议

- 若需要更大规模校验（如 `fib(1000)`），可加一条大数快速属性测试（Python int 任意精度，本实现天然支持）。
- 如接入项目级 coverage，可新增 `artifacts/code/conftest.py` 或调整 rootdir 以隔离主工程的覆盖率配置。
