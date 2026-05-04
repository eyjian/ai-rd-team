"""M1 真实 E2E 驱动脚本。

在工作区启动 ai-rd-team 引擎：initialize → start_run → 等待 → stop_run。

由主 Agent（CodeBuddy 会话）通过 bridge Skill 处理 intent 文件。
"""
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "driver.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("driver")

from ai_rd_team.adapter.bridge import FileBasedBridge
from ai_rd_team.engine.manager import TeamEnvironmentManager

WORKSPACE = Path(__file__).resolve().parent
RUNTIME = WORKSPACE / ".ai-rd-team" / "runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)


def main() -> int:
    bridge = FileBasedBridge(
        runtime_dir=RUNTIME,
        timeout_seconds=120,
        poll_interval_seconds=0.5,
    )
    engine = TeamEnvironmentManager(workspace=WORKSPACE, bridge=bridge)

    logger.info("=== Stage 1: initialize (会触发 _probe + _version 两个 intent) ===")
    engine.initialize(allow_onboarding=False, interactive=False)
    logger.info("initialize OK; capabilities=%s", engine.config.active_mode)

    logger.info("=== Stage 2: start_run (会触发 team_create + task + send_message) ===")
    ctx = engine.start_run(
        requirement=(
            "请实现一个 Python 函数 hello(name: str) -> str，"
            "返回 f'Hello, {name}!'。"
            "保存为 hello.py 放到 artifacts/code/ 目录。"
            "不需要单测，不需要其他文件。完成后发消息给 main 说你完成了。"
        ),
    )
    logger.info("start_run OK; run_id=%s members=%s", ctx.run_id, list(ctx.members))

    # Stage 3: 等待成员工作（M1 无法检测完成，等固定时长或者靠 state 文件）
    logger.info("=== Stage 3: wait for members to work (最多 180s) ===")
    deadline = time.time() + 180
    artifact_path = RUNTIME / "artifacts" / "code"
    while time.time() < deadline:
        files = list(artifact_path.glob("*.py")) if artifact_path.is_dir() else []
        if files:
            logger.info("artifact detected: %s", files)
            # 再等一点，让成员完成写入
            time.sleep(5)
            break
        time.sleep(3)

    logger.info("=== Stage 4: stop_run (会触发 shutdown_request + team_delete) ===")
    engine.stop_run(reason="test done")
    logger.info("stop_run OK; final state=%s", engine.state)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("driver failed")
        sys.exit(1)
