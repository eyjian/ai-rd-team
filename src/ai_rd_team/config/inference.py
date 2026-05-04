"""配置智能推断。

对应设计文档：openspec/specs/design/10-config-schema.md §2B（智能推断映射表）

推断优先级（§2B.5）：
    显式写入 advanced > 显式写入 basic > 引导输入 > 环境推断 > defaults
"""

from __future__ import annotations

import locale
import os
import platform
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 扫描文件时的最大深度（避免递归太深）
_MAX_SCAN_DEPTH = 3
# 扫描 .py / .go 文件时的样本数量上限（用于粗略判断"是否是 Go/Python 项目"）
_SAMPLE_LIMIT = 50

# 禁止写入的系统路径
_FORBIDDEN_PATHS = (
    "/etc/**",
    "/usr/**",
    "~/.ssh/**",
    "~/.aws/**",
    "~/.kube/**",
    "~/.docker/config.json",
    "~/.netrc",
)

# 默认预设的敏感命令黑名单（§2B.4）
_DEFAULT_COMMAND_BLACKLIST = (
    "rm -rf /",
    "rm -rf ~",
    "rm -rf *",
    "dd if=",
    "mkfs",
    ":(){ :|:& };:",  # fork bomb
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
)


@dataclass
class InferredConfig:
    """推断结果聚合。"""

    project: dict[str, Any] = field(default_factory=dict)
    tech_stack: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    web: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为嵌套 dict，可与其他配置层合并。"""
        return {
            "project": self.project,
            "tech_stack": self.tech_stack,
            "environment": self.environment,
            "web": self.web,
            "security": self.security,
            "logging": self.logging,
        }


class ConfigInference:
    """从环境和工作区推断配置字段。

    示例：
        inf = ConfigInference()
        inferred = inf.infer(Path.cwd())
        # inferred.project == {"name": "my-project", "workspace": Path(...)}
        # inferred.environment == {"display_currency": "CNY", ...}
    """

    def infer(self, workspace: Path) -> InferredConfig:
        """扫描工作区 + 环境，产出 InferredConfig。

        Args:
            workspace: 工作区根目录（通常是 Path.cwd()）
        """
        result = InferredConfig()
        result.project = self.infer_project_info(workspace)
        result.tech_stack = self.infer_tech_stack(workspace)
        result.environment = self.infer_environment()
        result.web = self.infer_web()
        result.security = self.infer_security(workspace)
        result.logging = self.infer_logging()
        return result

    # ------------------------------------------------------------
    # §2B.1 项目信息
    # ------------------------------------------------------------

    def infer_project_info(self, workspace: Path) -> dict[str, Any]:
        """推断 project.name / workspace / description。"""
        name = self._safe_project_name(workspace)
        description = self._read_readme_title(workspace)
        return {
            "name": name,
            "workspace": workspace,
            "description": description,
        }

    @staticmethod
    def _safe_project_name(workspace: Path) -> str:
        """从目录名推断项目名，处理 `.`/`_` 前缀等边界。"""
        name = workspace.name.lstrip("._") or "unnamed-project"
        return name

    @staticmethod
    def _read_readme_title(workspace: Path) -> str:
        """读取 README.md 的首个一级标题作为描述。"""
        for candidate in ("README.md", "README", "readme.md"):
            readme = workspace / candidate
            if not readme.is_file():
                continue
            try:
                for line in readme.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        return stripped[2:].strip()
            except OSError:
                return ""
        return ""

    # ------------------------------------------------------------
    # §2B.2 技术栈
    # ------------------------------------------------------------

    def infer_tech_stack(self, workspace: Path) -> dict[str, Any]:
        """扫描项目文件推断技术栈熟练度 + 偏好。"""
        proficiency = self._scan_proficiency(workspace)
        preferences = self._infer_preferences(workspace, proficiency)
        return {
            "proficiency": proficiency,
            "preferences": preferences,
        }

    @staticmethod
    def _scan_proficiency(workspace: Path) -> dict[str, bool]:
        """扫描文件系统判断语言/框架是否存在。

        只判断存在与否（粗粒度），不统计数量。
        """
        prof: dict[str, bool] = {}

        # 语言指纹：文件名 → 语言标记
        fingerprints: list[tuple[str, tuple[str, ...]]] = [
            ("python", ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")),
            ("go", ("go.mod", "go.sum")),
            ("rust", ("Cargo.toml",)),
            ("typescript", ("tsconfig.json",)),
            ("node", ("package.json",)),
            ("java", ("pom.xml", "build.gradle", "build.gradle.kts")),
        ]

        for lang, files in fingerprints:
            prof[lang] = any((workspace / f).exists() for f in files)

        # 前端框架：从 package.json 读取
        pkg_json = workspace / "package.json"
        if pkg_json.is_file():
            try:
                import json

                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                deps: dict[str, Any] = {}
                deps.update(data.get("dependencies", {}) or {})
                deps.update(data.get("devDependencies", {}) or {})
                prof["vue"] = "vue" in deps
                prof["react"] = "react" in deps
            except (OSError, ValueError):
                prof["vue"] = False
                prof["react"] = False
        else:
            prof["vue"] = False
            prof["react"] = False

        return prof

    @staticmethod
    def _infer_preferences(
        workspace: Path,
        proficiency: dict[str, bool],
    ) -> dict[str, str | None]:
        """根据已有代码推断后端/前端偏好。"""
        backend: str | None = None
        if proficiency.get("go"):
            backend = "go"
        elif proficiency.get("python"):
            backend = "python"
        elif proficiency.get("node"):
            backend = "node"
        elif proficiency.get("rust"):
            backend = "rust"
        elif proficiency.get("java"):
            backend = "java"

        frontend: str | None = None
        if proficiency.get("vue"):
            frontend = "vue"
        elif proficiency.get("react"):
            frontend = "react"
        elif (workspace / "web").is_dir() or (workspace / "frontend").is_dir():
            frontend = "unknown"

        return {
            "backend": backend,
            "frontend": frontend,
            "mobile": None,
        }

    # ------------------------------------------------------------
    # §2B.3 环境
    # ------------------------------------------------------------

    def infer_environment(self) -> dict[str, Any]:
        """推断 os / python 版本 / 币种等。"""
        py_ver = platform.python_version()
        return {
            "os_supported": platform.system(),
            "python_min": ".".join(py_ver.split(".")[:2]),  # e.g. "3.11"
            "display_currency": self._infer_currency(),
        }

    @staticmethod
    def _infer_currency() -> str:
        """按 locale 推断展示币种。"""
        # 优先 LANG 环境变量
        lang = os.environ.get("LANG") or os.environ.get("LC_ALL") or ""
        if "zh_CN" in lang or "zh-CN" in lang:
            return "CNY"

        # 兜底读取系统 locale（可能在某些环境抛 Error）
        try:
            current = locale.getlocale()
            if current and current[0] and "zh_CN" in current[0]:
                return "CNY"
        except (locale.Error, ValueError):
            pass

        return "USD"

    def infer_web(self) -> dict[str, Any]:
        """推断 Web 绑定 host / port。"""
        return {
            "host": "127.0.0.1",
            "port": self._find_free_port(start=8765, limit=50),
        }

    @staticmethod
    def _find_free_port(start: int, limit: int = 50) -> int:
        """查找一个空闲 TCP 端口，从 start 起累加 limit 次。"""
        for offset in range(limit):
            port = start + offset
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        # 全部占用时返回 start（让运行时再报错）
        return start

    def infer_logging(self) -> dict[str, Any]:
        """推断日志级别。"""
        level = "debug" if os.environ.get("DEBUG") == "1" else "info"
        return {"level": level}

    # ------------------------------------------------------------
    # §2B.4 安全
    # ------------------------------------------------------------

    def infer_security(self, workspace: Path) -> dict[str, Any]:
        """产出安全默认（文件访问 + 命令黑名单）。"""
        workspace_str = str(workspace.resolve())
        return {
            "file_access": {
                "writable": [
                    f"{workspace_str}/**",
                ],
                "readonly": [
                    f"{workspace_str}/.git/**",
                    f"{workspace_str}/.ai-rd-team/memory/decisions/**",
                ],
                "forbidden": list(_FORBIDDEN_PATHS),
            },
            "commands": {
                "blocked": list(_DEFAULT_COMMAND_BLACKLIST),
            },
        }
