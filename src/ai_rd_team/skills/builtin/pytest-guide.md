---
name: pytest-guide
description: Pytest 测试编写指南。在用 pytest 为 Python 项目编写单元测试或集成测试时使用，覆盖参数化、fixture、异常断言、mock、目录结构、覆盖率以及常见陷阱。
default_for: [developer, tester]
---

# Pytest Guide

## 适用场景

用 pytest 编写 Python 测试。

## 核心原则

- **一个测试只验一个事**：失败时能立刻定位
- **Arrange-Act-Assert**：三段式结构，清晰可读
- **快**：单测一秒内跑完，慢的标 `@pytest.mark.slow`

## 常用模式

### 基本用法

```python
def test_add_returns_sum():
    assert add(1, 2) == 3
```

### 参数化

```python
@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
])
def test_add(a, b, expected):
    assert add(a, b) == expected
```

### Fixture

```python
@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    (tmp_path / ".ai-rd-team").mkdir()
    return tmp_path

def test_init(tmp_workspace: Path):
    ...
```

- Scope：`function`（默认）/ `class` / `module` / `session`
- 清理用 `yield`：`yield value; cleanup()`

### 异常断言

```python
with pytest.raises(ValueError, match="invalid"):
    parse("xxx")
```

### Mock

```python
from unittest.mock import patch, MagicMock

def test_api(monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    ...

with patch("module.func") as m:
    m.return_value = "mocked"
    ...
```

## 目录结构

```
tests/
├── conftest.py          # 共享 fixture
├── unit/                # 单元测试
└── integration/         # 集成测试
```

`conftest.py` 的 fixture 自动对所在目录及子目录可见。

## 覆盖率

```bash
pytest --cov=src --cov-report=term-missing
```

目标：行覆盖率 ≥ 80%，关键模块 ≥ 95%。

## 禁止

- ❌ 测试之间有执行顺序依赖（用 fixture 隔离状态）
- ❌ 访问真实外部服务（DB / HTTP）而不 mock
- ❌ 在测试里 sleep（改用 fake clock 或 mock）
- ❌ 为了覆盖率写无断言的"烟雾测试"

## 常见陷阱

- **tmp_path vs tmp_path_factory**：函数级 vs session 级
- **monkeypatch 在 class fixture 不能用**：改用 `autouse=True` 函数 fixture
- **Windows 路径**：用 `Path` 不用字符串拼接
