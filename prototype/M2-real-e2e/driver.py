"""M2 真实 E2E 驱动脚本。

验证要点：
- Memory agent.d 注入到 developer prompt
- Skills builtin 注入到 developer prompt
- CostTracker 记录 spawn/message/runtime
- HookRunner 触发 run_started/run_stopped 自定义 Hook
- check_budget / cost_snapshot API 可用
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# 确保 ai_rd_team 可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "driver.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("m2-driver")

from ai_rd_team.adapter.bridge import FileBasedBridge
from ai_rd_team.engine.manager import TeamEnvironmentManager

WORKSPACE = Path(__file__).resolve().parent
RUNTIME = WORKSPACE / ".ai-rd-team" / "runtime"
QUOTA_HOME = WORKSPACE / "quota-home"  # 隔离，避免污染真实 ~/.ai-rd-team


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    QUOTA_HOME.mkdir(parents=True, exist_ok=True)

    bridge = FileBasedBridge(
        runtime_dir=RUNTIME,
        timeout_seconds=180,
        poll_interval_seconds=0.5,
    )
    engine = TeamEnvironmentManager(
        workspace=WORKSPACE,
        bridge=bridge,
        quota_home_dir=QUOTA_HOME,
    )

    logger.info("=== Stage 1: initialize ===")
    engine.initialize(allow_onboarding=False, interactive=False)
    logger.info("initialize OK; mode=%s", engine.config.active_mode)

    logger.info("=== Stage 2: start_run ===")
    ctx = engine.start_run(
        requirement=(
            "请严格按 .ai-rd-team/memory/agent.d/interface-contracts.md 里的接口契约，"
            "实现 fibonacci(n) 函数并保存为 fibonacci.py，放到 "
            ".ai-rd-team/runtime/artifacts/code/ 目录。"
            "完成后把 state/members/developer.yaml 的 status 更新为 done，"
            "并 send_message 给 main 汇报。"
        )
    )
    logger.info("start_run OK; run_id=%s members=%s", ctx.run_id, list(ctx.members))

    # Stage 3: 等待成员工作
    logger.info("=== Stage 3: wait for member ===")
    deadline = time.time() + 240
    artifact_path = RUNTIME / "artifacts" / "code"
    while time.time() < deadline:
        files = list(artifact_path.glob("*.py")) if artifact_path.is_dir() else []
        if files:
            logger.info("artifact detected: %s", files)
            time.sleep(5)
            break
        # 每 10 秒打印一次成本快照
        if int(time.time()) % 10 < 1:
            snap = engine.cost_snapshot()
            if snap:
                logger.info(
                    "cost: rp=%s/%s members=%s messages=%s minutes=%.1f",
                    snap.resource_points,
                    snap.rp_budget,
                    snap.member_spawn_count,
                    snap.message_count,
                    snap.runtime_minutes,
                )
        time.sleep(3)

    # Stage 4: 检查预算状态
    logger.info("=== Stage 4: check_budget ===")
    bc = engine.check_budget()
    if bc is not None:
        logger.info(
            "budget: action=%s reason=%s msg=%s",
            bc.action.value,
            bc.reason.value,
            bc.message,
        )

    logger.info("=== Stage 5: stop_run ===")
    engine.stop_run(reason="e2e-done")

    # 最终快照
    snap = engine.cost_snapshot()
    if snap:
        logger.info(
            "FINAL cost: rp=%s members=%s messages=%s broadcasts=%s minutes=%.1f iterations=%s",
            snap.resource_points,
            snap.member_spawn_count,
            snap.message_count,
            snap.broadcast_count,
            snap.runtime_minutes,
            snap.iteration_count,
        )

    logger.info("state=%s", engine.state)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("driver failed")
        sys.exit(1)
