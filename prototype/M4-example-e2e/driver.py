"""M4 Example E2E driver：复用 M3 的 driver + serve 合并架构。

专门用于跑 examples/01-smart-bookmark 验证示例可跑通。
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
SERVE_PORT = 8771


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(WORKSPACE / "driver.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def start_serve_thread(engine: TeamEnvironmentManager) -> None:
    app = create_app(workspace=WORKSPACE, engine=engine)
    cfg = uvicorn.Config(
        app, host=SERVE_HOST, port=SERVE_PORT, log_level="warning", access_log=False
    )
    server = uvicorn.Server(cfg)
    t = threading.Thread(target=server.run, daemon=True, name="serve-thread")
    t.start()
    for _ in range(20):
        if server.started:
            break
        time.sleep(0.1)


def main() -> int:
    setup_logging()
    logger = logging.getLogger("m4-driver")

    # 读取 REQUIREMENT.md 作为需求描述
    req_file = WORKSPACE / "REQUIREMENT.md"
    requirement = req_file.read_text(encoding="utf-8").strip() if req_file.is_file() else (
        "做一个叫 smart-bookmark 的命令行书签管理工具"
    )

    engine = TeamEnvironmentManager(
        workspace=WORKSPACE,
        quota_home_dir=WORKSPACE / "quota-home",
    )

    logger.info("stage 1: initialize")
    engine.initialize(allow_onboarding=False, interactive=False)

    logger.info("stage 2: start_serve（后台线程 %s:%d）", SERVE_HOST, SERVE_PORT)
    start_serve_thread(engine)
    logger.info("  Web 面板：http://%s:%d", SERVE_HOST, SERVE_PORT)

    logger.info("stage 3: start_run (requirement=%d 字符)", len(requirement))
    ctx = engine.start_run(requirement)
    logger.info("run started: id=%s members=%d", ctx.run_id, len(ctx.members))

    logger.info("stage 4: 等 90s（这个任务比 M3 复杂一些）")
    for i in range(90):
        time.sleep(1)
        if i % 15 == 14:
            snap = engine.cost_snapshot()
            res = engine.check_budget()
            logger.info(
                "t=%ds rp=%s ratio=%.2f action=%s",
                i + 1,
                snap.resource_points if snap else "-",
                snap.rp_usage_ratio if snap else 0.0,
                res.action.value if res else "-",
            )

    logger.info("stage 5: stop_run")
    engine.stop_run(reason="m4-example-e2e-done")
    logger.info("driver 完成")
    time.sleep(5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
