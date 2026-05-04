"""成员 Prompt 渲染器。

对应设计文档：openspec/specs/design/05-roles-skills.md §7

M1 采用字符串 Template（Python 标准库）而非 Jinja2，以减少依赖。
模板内置为多行字符串常量，不依赖文件系统。
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from ai_rd_team.config.models import EffectiveConfig, Role

# 角色 → 制品子目录映射（§7.5）
ROLE_TO_DIR: dict[str, str] = {
    "pm": "reports",
    "analyst": "requirements",
    "architect": "design",
    "developer": "code",
    "reviewer": "review",
    "tester": "test",
    "devops": "deployment",
}

# M1 内嵌模板（基于 P1 验证的有效格式）
# 用 Python string.Template 语法（$variable），避开 $$ 转义复杂度
_MEMBER_PROMPT_TEMPLATE = """# 身份与职责

你是 $display_name（$role_name）。

**Persona**：
$persona

**团队成员**：
$team_roster
（你可以直接通过 send_message 给上述任何成员发消息，不需要经过 main）

**当前任务**：
$project_description

**本次运行档位**：$run_mode


# 工作目录

所有产出文件必须写入：
`$workspace/.ai-rd-team/runtime/artifacts/$role_dir/`

每完成一个关键步骤，更新自己的状态到：
`$workspace/.ai-rd-team/runtime/state/members/$instance_name.yaml`

状态文件格式：
```yaml
name: $instance_name
role: $role_name
status: "working"      # idle / working / waiting / done / failed
current_task: "当前在做什么"
last_updated: "ISO 8601 时间戳"
progress: "50%"
produced_files: []
blocking_issues: []
```


# 你要做什么（职责清单）

$role_responsibilities

**期望产出**：
$expected_artifacts


# 协作约束

✅ **允许做的**：
- 与团队中其他成员自由 send_message（P2P）
- 读取 workspace 下的文件
- 写入 `$workspace/.ai-rd-team/runtime/artifacts/$role_dir/`
- 执行安全命令（如 pytest / go test / npm run 等）

❌ **禁止做的**：
- 不要反复请示 main（除非真的被卡住超过 15 分钟）
- 不要使用 broadcast（除非 run_mode = full 且确实必要）
- 不要修改 `.git/` / `.ai-rd-team/memory/decisions/`
- 不要执行危险命令（rm -rf / / dd / mkfs / shutdown 等）


# Skills（可用技能）

$skills_injected


# 记忆（背景知识）

$agent_d_memory_injected


# 关键要求

1. **自主决策**：你是专业的 $role_name，按你的判断推进工作。不需要每步都问 main。
2. **主动沟通**：有问题直接找相关队友，不要闷头做。
3. **写文件即汇报**：产出文件 + 更新 state 文件，Web 面板会自动展示你的进度。
4. **遇到真正的死局**：用 send_message 向 pm 报告（若无 pm 则向 main）。
5. **完成工作**：全部完成后，写一份 `report-$role_name.md` 到 artifacts/reports/，并 send_message 汇报。


# 当前已知的团队约定

$project_rules


# 等待起始消息

现在请等待启动消息。收到后开始工作。
"""


# 角色默认职责清单（M1 内置，M2+ 从 Role.responsibilities 字段读取）
_DEFAULT_RESPONSIBILITIES: dict[str, list[str]] = {
    "pm": [
        "拆解需求为可执行任务",
        "跟踪整体进度",
        "协调团队成员间的冲突",
        "整理总结报告",
    ],
    "analyst": [
        "深入理解用户需求",
        "产出需求文档 PRD",
        "识别关键用例和边界",
    ],
    "architect": [
        "设计系统架构和模块划分",
        "定义接口契约",
        "输出技术方案文档",
    ],
    "developer": [
        "按架构师的接口契约实现代码",
        "编写必要的单元测试",
        "主动与其他开发者协调共享依赖",
    ],
    "reviewer": [
        "评审代码质量、风格、潜在 bug",
        "向开发者提出具体的 issue",
        "跟进修复结果并复审",
    ],
    "tester": [
        "编写测试用例覆盖主要路径和异常",
        "执行测试并分析失败原因",
        "向开发者反馈可复现的 bug",
    ],
    "devops": [
        "准备部署清单和环境依赖",
        "编写 CI/CD 配置",
        "部署到目标环境",
    ],
}

_DEFAULT_ARTIFACTS: dict[str, list[str]] = {
    "pm": ["spec-project-plan.md", "report-final.md"],
    "analyst": ["spec-requirements.md", "data-user-stories.yaml"],
    "architect": ["spec-design.md", "data-interfaces.yaml"],
    "developer": ["实现代码（写入项目源码目录）", "对应单元测试"],
    "reviewer": ["spec-review-{module}.md"],
    "tester": ["测试代码", "result-test-{module}.md"],
    "devops": ["spec-deployment.md", "部署脚本"],
}


@dataclass
class RenderedPrompt:
    """渲染结果。"""

    content: str
    instance_name: str
    role_name: str
    estimated_tokens: int

    def __str__(self) -> str:
        return self.content


class PromptRenderer:
    """成员 prompt 渲染器。

    典型用法：
        renderer = PromptRenderer()
        rendered = renderer.render(
            role=config.roles["architect"],
            instance_name="architect",
            config=config,
            team_roster=[("architect", "architect"), ("developer_1", "developer")],
        )
        adapter.spawn_member(..., rendered_prompt=rendered.content)
    """

    def __init__(self, template_override: str | None = None):
        """
        Args:
            template_override: 自定义模板字符串（一般用于测试）
        """
        self._template = Template(template_override or _MEMBER_PROMPT_TEMPLATE)

    def render(
        self,
        role: Role,
        instance_name: str,
        config: EffectiveConfig,
        team_roster: list[tuple[str, str]],
        skills_injected: str = "",
        agent_d_memory_injected: str = "",
    ) -> RenderedPrompt:
        """渲染成员 prompt。

        Args:
            role: 角色定义
            instance_name: 实例名（architect / developer_1 等）
            config: 完整配置
            team_roster: [(instance_name, role_name), ...]
            skills_injected: M1 可留空，M2 由 SkillsLoader 注入
            agent_d_memory_injected: M1 可留空，M2 由 MemoryManager 注入
        """
        display_name = self._resolve_display_name(role, instance_name)
        role_dir = ROLE_TO_DIR.get(role.name, role.name)
        run_mode = config.active_mode

        content = self._template.safe_substitute(
            display_name=display_name,
            role_name=role.name,
            persona=role.persona or f"你是 {role.name}，请按专业判断推进工作。",
            team_roster=self._format_roster(team_roster),
            project_description=config.project.description or "（需求由启动消息提供）",
            run_mode=run_mode,
            workspace=str(config.project.workspace),
            role_dir=role_dir,
            instance_name=instance_name,
            role_responsibilities=self._format_responsibilities(role),
            expected_artifacts=self._format_artifacts(role),
            skills_injected=skills_injected or "（M1：暂无 Skills 注入）",
            agent_d_memory_injected=agent_d_memory_injected or "（M1：暂无共享记忆）",
            project_rules=self._format_rules(config.rules),
        )

        return RenderedPrompt(
            content=content,
            instance_name=instance_name,
            role_name=role.name,
            estimated_tokens=self.estimate_tokens(content),
        )

    # ------------------------------------------------------------
    # 格式化辅助
    # ------------------------------------------------------------

    @staticmethod
    def _resolve_display_name(role: Role, instance_name: str) -> str:
        """display_name 解析：有 role.display_name 用之，否则用 instance_name。"""
        if role.display_name:
            # 若是可伸缩角色，可能需要附加数字
            if role.scalable and "_" in instance_name:
                idx = instance_name.rsplit("_", 1)[-1]
                return f"{role.display_name}{idx}"
            return role.display_name
        return instance_name

    @staticmethod
    def _format_roster(roster: list[tuple[str, str]]) -> str:
        """格式化 team_roster 为多行字符串。"""
        if not roster:
            return "（独自工作）"
        return "\n".join(f"- {instance}（{role}）" for instance, role in roster)

    @staticmethod
    def _format_responsibilities(role: Role) -> str:
        """从内置清单取，若无则回退到泛泛描述。"""
        items = _DEFAULT_RESPONSIBILITIES.get(role.name)
        if not items:
            return f"作为 {role.name}，按专业判断推进本角色相关的工作。"
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _format_artifacts(role: Role) -> str:
        items = _DEFAULT_ARTIFACTS.get(role.name)
        if not items:
            return "（按任务需要产出）"
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _format_rules(rules_dict: dict) -> str:  # type: ignore[type-arg]
        """rules 可能是 dict（含 list 字段）或空。M1 最简化处理。"""
        if not rules_dict:
            return "（无特殊约定）"

        lines: list[str] = []
        for key, value in rules_dict.items():
            if isinstance(value, list):
                for item in value:
                    lines.append(f"- [{key}] {item}")
            elif value:
                lines.append(f"- [{key}] {value}")

        return "\n".join(lines) if lines else "（无特殊约定）"

    # ------------------------------------------------------------
    # Token 估算（粗略）
    # ------------------------------------------------------------

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """M1 粗估：英文按字符 /4，中文按字符 /1.5 加权。

        更精确的估算在 M2 的 cost 模块实现。
        """
        if not text:
            return 0
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - cn_chars
        return int(cn_chars / 1.5) + int(other_chars / 4)


# ============================================================
# 内置角色工厂（M1 默认角色定义）
# ============================================================


# 每个角色的默认 Skills 引用（M2 + T2.4）
# 说明：
# - 这些 Skills 来自 builtin（随包分发）或 workspace（用户项目自定义）
# - 用户可通过 config.advanced.yaml 的 roles.<name>.skills 覆盖
_DEFAULT_ROLE_SKILLS: dict[str, tuple[str, ...]] = {
    "pm": (),
    "analyst": (),
    "architect": ("code-review-checklist",),
    "developer": ("python-best-practices", "pytest-guide"),
    "reviewer": ("code-review-checklist", "python-best-practices"),
    "tester": ("pytest-guide",),
    "devops": (),
}

# 每个角色的默认 agent.d 记忆范围（M2 + T2.4）
# agent.d 是启动加载、token 敏感的，只引用最常用的几个
_DEFAULT_ROLE_MEMORY_SCOPE: dict[str, dict[str, list[str]]] = {
    "pm": {"agent_d": ["team-roster", "current-phase", "key-decisions"]},
    "analyst": {"agent_d": ["domain-terms", "current-phase"]},
    "architect": {
        "agent_d": [
            "tech-stack-selected",
            "interface-contracts",
            "key-decisions",
        ]
    },
    "developer": {
        "agent_d": ["tech-stack-selected", "interface-contracts"]
    },
    "reviewer": {
        "agent_d": ["tech-stack-selected", "key-decisions"]
    },
    "tester": {"agent_d": ["interface-contracts"]},
    "devops": {"agent_d": ["tech-stack-selected"]},
}


def builtin_roles() -> dict[str, Role]:
    """返回 M2 内置的 7 个角色定义（含默认 Skills 和 memory_scope）。

    用户可通过 config.advanced.yaml 的 roles.<name> 覆盖任意字段。
    """
    specs: list[tuple[str, str, str, bool, int, int]] = [
        # (name, display_name, persona, scalable, default_instances, max_instances)
        (
            "pm",
            "周立项",
            "你是项目经理周立项，经验丰富，擅长协调和推进。",
            False,
            1,
            1,
        ),
        (
            "analyst",
            "沈需求",
            "你是需求分析师沈需求，善于从用户描述中提炼核心价值和边界。",
            False,
            1,
            1,
        ),
        (
            "architect",
            "陈架构",
            "你是架构师陈架构，注重接口清晰、模块解耦、可演进。",
            False,
            1,
            1,
        ),
        (
            "developer",
            "林",
            "你是开发工程师，按接口契约实现代码，主动与队友协调。",
            True,
            2,
            5,
        ),
        (
            "reviewer",
            "王",
            "你是代码检视者，关注质量、风格、潜在 bug，给出具体可操作的建议。",
            True,
            1,
            3,
        ),
        (
            "tester",
            "赵",
            "你是测试工程师，擅长从边界/异常/正常三类用例覆盖功能。",
            True,
            1,
            3,
        ),
        (
            "devops",
            "钱",
            "你是 DevOps，负责部署、CI/CD、环境准备。",
            False,
            1,
            1,
        ),
    ]

    result: dict[str, Role] = {}
    for name, display, persona, scalable, default_i, max_i in specs:
        result[name] = Role(
            name=name,
            display_name=display,
            persona=persona,
            scalable=scalable,
            default_instances=default_i,
            max_instances=max_i,
            skills=_DEFAULT_ROLE_SKILLS.get(name, ()),
            memory_scope=dict(_DEFAULT_ROLE_MEMORY_SCOPE.get(name, {})),
        )
    return result


__all__ = [
    "PromptRenderer",
    "RenderedPrompt",
    "ROLE_TO_DIR",
    "builtin_roles",
]
