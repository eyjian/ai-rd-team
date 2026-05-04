"""原子文件操作 + 锁追加工具。

对应设计文档：openspec/specs/design/07-artifacts.md §8（file_ops 工具）

三种策略：
- atomic_write（S2）：先写临时，再 rename 到目标 → 保证读永远不看到半成品
- locked_append（S3）：多进程共享日志文件，fcntl 锁
- read_if_exists：安全读取可能不存在的文件
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import tempfile
import threading
from pathlib import Path
from typing import Any

# Windows 降级时的进程内锁池（按文件路径复用）
_win_locks: dict[str, threading.Lock] = {}
_win_locks_guard = threading.Lock()


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """原子写：先写临时文件，再 os.replace 到目标。

    保证：
    - 任何时刻读取 path 都能读到完整内容（旧值或新值，不会读到一半）
    - 写失败时临时文件被清理

    适用场景：状态文件、意图文件、配置文件等。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def atomic_write_json(
    path: Path,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """JSON 版本的原子写（常用场景，避免调用方重复 json.dumps）。"""
    atomic_write(path, json.dumps(data, indent=indent, ensure_ascii=ensure_ascii))


def locked_append(path: Path, content: str, encoding: str = "utf-8") -> None:
    """带锁追加：多进程/线程共享文件。

    - Linux/macOS：fcntl.LOCK_EX
    - Windows：优先 portalocker，否则降级为进程内线程锁

    典型场景：events.jsonl / adapter-calls.jsonl。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        _append_windows(path, content, encoding)
    else:
        _append_fcntl(path, content, encoding)


def _append_fcntl(path: Path, content: str, encoding: str) -> None:
    import fcntl  # 仅 Linux/Mac 可用

    with open(path, "a", encoding=encoding) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _append_windows(path: Path, content: str, encoding: str) -> None:
    """Windows 降级：有 portalocker 用它，否则进程内锁。"""
    try:
        import portalocker  # type: ignore[import-untyped]

        with open(path, "a", encoding=encoding) as f:
            portalocker.lock(f, portalocker.LOCK_EX)
            try:
                f.write(content)
                f.flush()
            finally:
                portalocker.unlock(f)
        return
    except ImportError:
        pass

    # 降级为进程内线程锁（不跨进程安全，但够 CLI 单进程使用）
    key = str(path.resolve())
    with _win_locks_guard:
        lock = _win_locks.setdefault(key, threading.Lock())
    with lock, open(path, "a", encoding=encoding) as f:
        f.write(content)
        f.flush()


def read_if_exists(path: Path, encoding: str = "utf-8") -> str | None:
    """读取文件，不存在时返回 None（避免 try/except FileNotFoundError 样板代码）。"""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding=encoding)
    except OSError:
        return None


def read_json_if_exists(path: Path) -> Any | None:
    """JSON 版 read_if_exists。无效 JSON 时返回 None（不抛异常）。"""
    text = read_if_exists(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None
