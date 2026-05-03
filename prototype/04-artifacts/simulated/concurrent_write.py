"""P4 参考实现：三种并发写策略对比。

用法：
    python concurrent_write.py

将依次运行 4 个测试场景，输出对比结论。
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path


TEST_DIR = Path(__file__).parent.parent / "results" / "concurrent-test"


def setup() -> None:
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True, exist_ok=True)


def test_different_files(num_threads: int = 10) -> dict:
    """测试 1：N 个线程并发写 N 个不同文件。"""
    results: list[tuple[int, bool, str]] = []

    def worker(tid: int) -> None:
        path = TEST_DIR / f"worker-{tid}.txt"
        content = f"Thread {tid} at {time.time()}\n" * 100
        try:
            path.write_text(content)
            # 立即读回校验
            read_back = path.read_text()
            ok = read_back == content
            results.append((tid, ok, "ok" if ok else "corrupted"))
        except Exception as e:
            results.append((tid, False, str(e)))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    success = sum(1 for _, ok, _ in results if ok)
    return {
        "test": "different_files",
        "total": num_threads,
        "success": success,
        "failed": num_threads - success,
        "verdict": "✅ 完全安全" if success == num_threads else "❌ 有失败",
    }


def test_same_file_unsafe(num_threads: int = 10) -> dict:
    """测试 2：N 个线程写同一文件，无保护（反面教材）。"""
    target = TEST_DIR / "shared-unsafe.txt"
    target.write_text("")

    def worker(tid: int) -> None:
        # 每个线程试图追加自己的标记
        with target.open("a") as f:
            f.write(f"[THREAD-{tid}]" + "x" * 1000 + "\n")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    content = target.read_text()
    markers = [f"[THREAD-{i}]" for i in range(num_threads)]
    present = sum(1 for m in markers if m in content)
    interleaved = any(content.count(m) != 1 for m in markers)

    return {
        "test": "same_file_unsafe",
        "markers_present": present,
        "markers_expected": num_threads,
        "verdict": "⚠️ 仅 Python GIL 保护，非跨进程安全" if present == num_threads and not interleaved
                    else "❌ 存在交错/丢失",
    }


def atomic_write(path: Path, content: str) -> None:
    """原子写：先写 .tmp，再 rename。"""
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def test_same_file_atomic(num_threads: int = 10) -> dict:
    """测试 3：N 个线程写同一文件，用原子 rename 保护。
    
    注意：原子 rename 只保证"读到的是完整的某一版本"，
    不保证"所有写入都保留"——这是 last-write-wins。
    """
    target = TEST_DIR / "shared-atomic.txt"

    def worker(tid: int) -> None:
        content = f"Winner is thread {tid}\n" + "x" * 1000
        atomic_write(target, content)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 验证是否是完整内容（不是半写）
    content = target.read_text()
    valid = content.startswith("Winner is thread ") and content.endswith("x" * 1000)

    return {
        "test": "same_file_atomic_rename",
        "final_content_valid": valid,
        "strategy": "last-write-wins（不保留所有写入）",
        "verdict": "✅ 最终内容完整" if valid else "❌ 内容损坏",
    }


def test_same_file_locked(num_threads: int = 10) -> dict:
    """测试 4：N 个线程写同一文件，用文件锁保护。
    
    用 fcntl（Linux/Mac）或用互斥锁模拟。
    """
    target = TEST_DIR / "shared-locked.txt"
    target.write_text("")

    try:
        import fcntl
        has_fcntl = True
    except ImportError:
        has_fcntl = False

    def worker(tid: int) -> None:
        marker = f"[THREAD-{tid}]" + "x" * 100 + "\n"
        if has_fcntl:
            with target.open("a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(marker)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            # 降级用 Python 锁
            with _py_lock:
                with target.open("a") as f:
                    f.write(marker)

    _py_lock = threading.Lock()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    content = target.read_text()
    markers = [f"[THREAD-{i}]" for i in range(num_threads)]
    all_present = all(m in content for m in markers)

    return {
        "test": "same_file_locked",
        "used_fcntl": has_fcntl,
        "all_markers_present": all_present,
        "verdict": "✅ 所有写入都保留" if all_present else "❌ 有丢失",
    }


def main() -> None:
    setup()
    tests = [
        test_different_files,
        test_same_file_unsafe,
        test_same_file_atomic,
        test_same_file_locked,
    ]

    print("=" * 60)
    print("P4 并发写策略对比")
    print("=" * 60)

    for fn in tests:
        result = fn()
        print(f"\n>>> {result['test']}")
        for k, v in result.items():
            if k == "test":
                continue
            print(f"    {k}: {v}")

    print("\n" + "=" * 60)
    print("建议（写入 results/conclusion.md）：")
    print("  S1（不同文件）：ai-rd-team 默认策略，简单安全")
    print("  S2（原子 rename）：用于单一状态文件（如 team-state.json）")
    print("  S3（文件锁）：用于日志追加等场景")
    print("=" * 60)


if __name__ == "__main__":
    main()
