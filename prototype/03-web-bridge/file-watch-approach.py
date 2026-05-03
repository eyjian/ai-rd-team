"""P3 Demo 1：基于文件监听的 Web Bridge 最小实现。

演示：
- 启动后监听 ./watched/ 目录
- 每次文件新增/修改都打印事件
- 可观察监听延迟

如未安装 watchdog，会降级到简单轮询。

用法：
    python file-watch-approach.py         # 启动监听
    # 另开终端：
    echo "hello" > watched/test1.txt      # 触发事件
    echo "world" >> watched/test1.txt     # 触发事件
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

WATCH_DIR = Path(__file__).parent / "watched"
WATCH_DIR.mkdir(exist_ok=True)


def poll_approach() -> None:
    """降级方案：简单轮询。"""
    print(f"[poll] 监听 {WATCH_DIR}，间隔 0.5s...")
    seen: dict[Path, float] = {}

    while True:
        for path in WATCH_DIR.rglob("*"):
            if path.is_file():
                mtime = path.stat().st_mtime
                if path not in seen:
                    print(f"[新增] {path.relative_to(WATCH_DIR)} @ {mtime:.3f}")
                    seen[path] = mtime
                elif seen[path] != mtime:
                    print(f"[修改] {path.relative_to(WATCH_DIR)} @ {mtime:.3f}")
                    seen[path] = mtime
        # 删除检测
        for path in list(seen.keys()):
            if not path.exists():
                print(f"[删除] {path.relative_to(WATCH_DIR)}")
                del seen[path]
        time.sleep(0.5)


def watchdog_approach() -> None:
    """优选方案：用 watchdog 库。"""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print("[降级] 未安装 watchdog，切换到轮询模式")
        poll_approach()
        return

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            rel = Path(event.src_path).relative_to(WATCH_DIR)
            ts = time.time()
            print(f"[{event.event_type:7}] {rel} @ {ts:.3f}")

    obs = Observer()
    obs.schedule(Handler(), str(WATCH_DIR), recursive=True)
    obs.start()
    print(f"[watchdog] 监听 {WATCH_DIR}")
    print("请在另一个终端 touch/写入该目录下的文件...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


if __name__ == "__main__":
    if "--poll" in sys.argv:
        poll_approach()
    else:
        watchdog_approach()
