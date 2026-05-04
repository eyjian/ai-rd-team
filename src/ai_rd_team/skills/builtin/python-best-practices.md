# Python Best Practices

## 适用场景

编写 Python 代码的所有场景（库、CLI、Web 服务、脚本）。

## 核心原则

- **类型注解优先**：所有公共函数必须有完整类型注解（`def foo(x: int) -> str:`）
- **dataclass > dict**：结构化数据优先用 `@dataclass(frozen=True)` 而非字典
- **pathlib > os.path**：路径操作一律用 `pathlib.Path`
- **显式 > 隐式**：避免 `from x import *`，避免全局可变状态
- **小函数**：一个函数做好一件事，行数尽量控制在 30 行以内

## 常用模式

### 异常处理
- 只捕获**具体**异常，不用裸 `except:`
- `raise X from original_error` 保留异常链
- 自定义异常继承专属基类（如 `class MyError(Exception): ...`）

### 路径与 IO
- 文本文件：`path.read_text(encoding="utf-8")` / `path.write_text(s, encoding="utf-8")`
- 二进制：`path.read_bytes()` / `path.write_bytes(b)`
- 关键文件用原子写：写 tmp + `os.replace`

### 并发
- CPU 密集：`concurrent.futures.ProcessPoolExecutor`
- IO 密集：`asyncio` 或 `ThreadPoolExecutor`
- 避免在 asyncio 里调同步阻塞 IO（必要时 `loop.run_in_executor`）

### 测试
- 单测文件放 `tests/unit/`，集成测试放 `tests/integration/`
- 函数命名 `test_<被测对象>_<场景>_<期望>`
- 用 `pytest.fixture` 而非 setUp/tearDown
- mock 外部依赖，不 mock 自己的模块

## 禁止

- ❌ 改标准库对象（如 monkeypatch `list.append`）
- ❌ 使用 `exec()` / `eval()` 处理用户输入
- ❌ 用 `is` 比较字符串（应用 `==`）
- ❌ 把 `mutable default arg`（如 `def foo(x=[])`）
- ❌ 在 `__init__` 里做重 IO（懒加载 + 显式 initialize 方法）

## 工具链

- **格式化 + Lint**：`ruff check` + `ruff format`（替代 black + flake8 + isort）
- **类型检查**：`mypy --strict`（或至少开启 `disallow_untyped_defs`）
- **测试**：`pytest` + `pytest-cov`（覆盖率 ≥ 80%）
- **依赖管理**：`pyproject.toml`（PEP 517/518），优先 `uv` 或 `pip`

## 参考

- PEP 8 / PEP 20 / PEP 484
- Ruff 规则集：https://docs.astral.sh/ruff/rules/
