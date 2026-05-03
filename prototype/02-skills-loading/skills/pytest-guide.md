# pytest 使用指南（测试用 Skill）

## 核心要求

- **必须使用 pytest**，不要用 `unittest`
- **必须使用 `pytest.fixture`** 而非 `setUp/tearDown`
- **优先使用参数化**（`@pytest.mark.parametrize`）减少重复代码

## 测试文件命名

- 测试文件：`test_<module>.py`
- 测试函数：`test_<behavior>` 或 `test_<behavior>_when_<condition>`

## 典型结构

```python
import pytest
from calculator import calc


@pytest.fixture
def simple_values():
    return 1, 2


@pytest.mark.parametrize("op,a,b,expected", [
    ("+", 1, 2, 3),
    ("-", 5, 3, 2),
    ("*", 3, 4, 12),
    ("/", 10, 2, 5),
])
def test_calc_basic(op, a, b, expected):
    assert calc(op, a, b) == expected


def test_calc_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        calc("/", 1, 0)
```

## 禁止

- ❌ 使用 `unittest.TestCase`
- ❌ 使用 `setUp`/`tearDown`
- ❌ 在测试中做实际网络/磁盘 IO（必要时用 fixture + tmp_path）
