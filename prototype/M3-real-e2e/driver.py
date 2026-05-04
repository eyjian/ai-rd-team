"""M3 真实 E2E driver：driver + serve 共享同一 Engine。

启动方式：
    python3 driver.py

行为：
- 读取 ``.ai-rd-team/config.yaml``（若不存在，请先通过 Web 面板引导生成）
- 初始化 Engine
- 在后台线程启动 Web 面板（127.0.0.1:8770），与 Engine 共享
- 启动 run
- 等待成员工作 45 秒（观察面板）
- stop_run
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

import uvicorn

from ai_rd_team.engine.manager import TeamEnvironmentManager
from ai_rd_team.service.app import create_app

WORKSPACE = Path(__file__).resolve().parent
SERVE_HOST = "127.0.0.1"
SERVE_PORT = 8770


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(WORKSPACE / "driver.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def start_serve_thread(engine: TeamEnvironmentManager) -> threading.Thread:
    """在后台线程启动 Web 面板（与 Engine 共享）。"""
    app = create_app(workspace=WORKSPACE, engine=engine)
    cfg = uvicorn.Config(
        app,
        host=SERVE_HOST,
        port=SERVE_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(cfg)

    def _run() -> None:
        server.run()

    t = threading.Thread(target=_run, daemon=True, name="serve-thread")
    t.start()
    # 等待 uvicorn 启动
    for _ in range(20):
        if server.started:
            break
        time.sleep(0.1)
    return t


def main() -> int:
    setup_logging()
    logger = logging.getLogger("m3-driver")

    config_path = WORKSPACE / ".ai-rd-team" / "config.yaml"
    if not config_path.is_file():
        logger.error(
            "config.yaml 不存在：%s\n"
            "先启动一个只读 serve 来走 Web 引导：\n"
            "  ai-rd-team serve --port %d -w %s\n"
            "在浏览器打开 http://%s:%d，完成引导再重跑本脚本。",
            config_path,
            SERVE_PORT,
            WORKSPACE,
            SERVE_HOST,
            SERVE_PORT,
        )
        return 1

    engine = TeamEnvironmentManager(
        workspace=WORKSPACE,
        quota_home_dir=WORKSPACE / "quota-home",
    )

    logger.info("stage 1: initialize")
    engine.initialize(allow_onboarding=False, interactive=False)

    logger.info("stage 2: start_serve（后台线程 %s:%d）", SERVE_HOST, SERVE_PORT)
    start_serve_thread(engine)
    logger.info("  Web 面板：http://%s:%d", SERVE_HOST, SERVE_PORT)

    logger.info("stage 3: start_run")
    ctx = engine.start_run("M3 E2E：实现斐波那契并验证面板实时刷新")
    logger.info(
        "run started: id=%s members=%d",
        ctx.run_id,
        len(ctx.members),
    )

    logger.info("stage 4: wait 45s（浏览器打开面板观察实时刷新）")
    for i in range(45):
        time.sleep(1)
        if i % 10 == 9:
            snap = engine.cost_snapshot()
            result = engine.check_budget()
            logger.info(
                "t=%ds rp=%s ratio=%.2f action=%s",
                i + 1,
                snap.resource_points if snap else "-",
                snap.rp_usage_ratio if snap else 0.0,
                result.action.value if result else "-",
            )

    logger.info("stage 5: stop_run")
    engine.stop_run(reason="m3-e2e-done")

    logger.info("driver 完成；面板继续保留 8 秒以便查看最终状态")
    time.sleep(8)
    return 0


if __name__ == "__main__":
    sys.exit(main())
