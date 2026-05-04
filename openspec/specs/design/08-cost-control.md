# ai-rd-team 详细设计 - 08 成本控制

> 文档版本：v1.0
> 日期：2026-05-04
> 颗粒度：中等详细
> 依赖：`00-overview.md`、`01-engine.md`、`10-config-schema.md`
> 头脑风暴相关：§21 分档运行模式与成本控制
> 原型相关：P5 Resource Points 权重 v1 校准

---

## 1. 目的与范围

### 1.1 目的
定义 ai-rd-team 的**成本追踪、档位管理、预算控制、模型降级**机制。这是第一期最关键的可用性保障——AI 时代成本不可控会直接劝退用户。

### 1.2 范围
- CostTracker 实时计量
- 三档运行模式（Lite / Standard / Full）
- 多级时间窗口额度（单次/日/周/月）
- smart_pause 智能暂停
- 模型降级（第一期半自动 / 第二期全自动）
- 事后记录与权重校准
- 多币种支持

### 1.3 非目标
- ❌ 精确 token 计费（CodeBuddy 未暴露 API，用估算）
- ❌ 运行时工具级模型切换（第一期 CodeBuddy 限制，半自动）
- ❌ 企业中央额度服务实现（第二期）

---

## 2. 核心概念

### 2.1 Resource Points（RP）

统一计量单位。不依赖具体模型价格。基于 P5 校准 v1 权重：

```
per_member_spawn:     40      # 每派发 1 个成员
per_message:          2       # 每条 P2P 消息
per_broadcast_target: 2       # 广播每个接收者
per_minute_runtime:   5       # 每分钟运行
per_iteration:        15      # 每轮评审/修复迭代
```

**基准**：`100 tokens ≈ 1 Resource Point`（Sonnet 定价下约 ¥0.002/RP）。

### 2.2 三档预算

基于 P5 校准：

| 档位 | max_resource_points | 对应场景 |
|------|---------------------|---------|
| 🟢 Lite | 120 | Bug 修复 / 小改动 |
| 🟡 Standard | 400 | 单模块开发 |
| 🔴 Full | 1500 | 复杂系统 |

### 2.3 四层额度

| 层级 | 典型值 | 触发行为 |
|------|-------|---------|
| 单次（per_run） | = 档位预算 | smart_pause |
| 日（per_day） | 2000 RP | block_new_run |
| 周（per_week） | 10000 RP | warn_and_block |
| 月（per_month） | 30000 RP | block_and_report |

---

## 3. CostTracker 接口

```python
# ai_rd_team/cost/tracker.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal


class BudgetAction(str, Enum):
    CONTINUE = "continue"
    WARN = "warn"
    SMART_PAUSE = "smart_pause"
    BLOCK = "block"


@dataclass
class CostSnapshot:
    """某时刻的成本快照。"""
    run_id: str
    mode: str
    timestamp: datetime
    # 计数
    member_spawn_count: int = 0
    message_count: int = 0
    broadcast_target_count: int = 0
    runtime_minutes: float = 0.0
    iteration_count: int = 0
    # Resource Points
    resource_points: int = 0
    # 额度剩余
    run_budget_remaining: int = 0
    day_budget_remaining: int = 0
    week_budget_remaining: int = 0
    month_budget_remaining: int = 0


class CostTracker:
    """成本追踪器。
    
    职责：
    - 实时记录成员 spawn / 消息 / 迭代等事件
    - 定期更新 resource-points.yaml
    - 检查预算 + 触发 smart_pause
    - 支持模型降级提示（第一期半自动）
    """
    
    def __init__(
        self,
        config: "CostControlConfig",
        workspace: Path,
    ):
        self.config = config
        self.workspace = workspace
        self._snapshot: CostSnapshot | None = None
        self._start_ts: datetime | None = None
        self._warn_threshold_triggered = False
        self._fallback_triggered = False
    
    # ===== 生命周期 =====
    
    def start_run(self, run_id: str, mode: Literal["lite", "standard", "full"]) -> None:
        """开始新运行。"""
        self._start_ts = datetime.now()
        self._snapshot = CostSnapshot(
            run_id=run_id,
            mode=mode,
            timestamp=self._start_ts,
            run_budget_remaining=self._current_budget().max_resource_points,
        )
        self._load_quota_state()
    
    def end_run(self) -> CostSnapshot:
        """结束运行，持久化到 archive/。"""
        self._save_quota_state()
        return self._snapshot
    
    # ===== 记录事件 =====
    
    def record_spawn(self) -> None:
        """记录一次成员 spawn。"""
        self._snapshot.member_spawn_count += 1
        self._snapshot.resource_points += self.config.weights.per_member_spawn
        self._after_change()
    
    def record_message(self, from_: str, to: str, msg_type: str = "message") -> None:
        """记录一条消息。"""
        self._snapshot.message_count += 1
        self._snapshot.resource_points += self.config.weights.per_message
        self._after_change()
    
    def record_broadcast(self, recipient_count: int) -> None:
        """记录一次广播。"""
        self._snapshot.broadcast_target_count += recipient_count
        self._snapshot.resource_points += recipient_count * self.config.weights.per_broadcast_target
        self._after_change()
    
    def record_iteration(self, iteration_type: str = "review") -> None:
        """记录一轮迭代（评审/修复）。"""
        self._snapshot.iteration_count += 1
        self._snapshot.resource_points += self.config.weights.per_iteration
        self._after_change()
    
    def update_runtime(self) -> None:
        """刷新运行时长（定期由引擎调用）。"""
        if self._start_ts:
            minutes = (datetime.now() - self._start_ts).total_seconds() / 60.0
            delta = minutes - self._snapshot.runtime_minutes
            self._snapshot.runtime_minutes = minutes
            self._snapshot.resource_points += int(delta * self.config.weights.per_minute_runtime)
            self._after_change()
    
    # ===== 查询 =====
    
    def snapshot(self) -> CostSnapshot:
        """返回当前快照的副本。"""
        return self._snapshot
    
    def check_budget(self) -> BudgetAction:
        """检查当前预算状态，返回应采取的动作。"""
        snap = self._snapshot
        budget = self._current_budget()
        
        # 检查单次预算
        if snap.resource_points >= budget.max_resource_points:
            return BudgetAction.SMART_PAUSE
        
        # 检查降级阈值
        if (
            not self._fallback_triggered
            and self.config.model_fallback.enabled
            and snap.resource_points >= int(budget.max_resource_points * self.config.model_fallback.trigger_threshold)
        ):
            return BudgetAction.WARN  # 建议降级
        
        # 检查时间窗口
        if snap.day_budget_remaining <= 0:
            return BudgetAction.BLOCK
        if snap.month_budget_remaining <= 0:
            return BudgetAction.BLOCK
        
        # 检查资源硬限
        if snap.member_spawn_count > budget.max_members:
            return BudgetAction.SMART_PAUSE
        if snap.message_count > budget.max_messages:
            return BudgetAction.SMART_PAUSE
        if snap.broadcast_target_count > budget.max_broadcasts * self._avg_team_size():
            return BudgetAction.WARN
        
        return BudgetAction.CONTINUE
    
    # ===== 事后记录 =====
    
    def prompt_user_to_record_actual(self) -> None:
        """运行结束后引导用户填入 CodeBuddy 面板看到的真实 token。
        
        写入 .ai-rd-team/runtime/cost/post-run.jsonl，供未来权重校准用。
        """
        # 实现：CLI 交互或 Web 面板表单
        ...
    
    def load_historical_calibration(self) -> dict:
        """加载历史真实消耗，用于校准建议。"""
    
    # ===== 辅助 =====
    
    def _current_budget(self) -> "Budget":
        """根据当前档位返回对应预算。"""
        return {
            "lite": self.config.budget_lite,
            "standard": self.config.budget_standard,
            "full": self.config.budget_full,
        }[self._snapshot.mode]
    
    def _after_change(self) -> None:
        """每次事件后：写文件 + 检查预算 + 触发 Hook。"""
        self._persist_snapshot()
        action = self.check_budget()
        if action != BudgetAction.CONTINUE:
            self._notify_action(action)
    
    def _persist_snapshot(self) -> None:
        """写到 runtime/cost/resource-points.yaml（原子写）。"""
        import yaml
        from ai_rd_team.shared.file_ops import atomic_write
        
        path = self.workspace / ".ai-rd-team" / "runtime" / "cost" / "resource-points.yaml"
        atomic_write(path, yaml.safe_dump(self._snapshot_to_dict(), allow_unicode=True))
    
    def _load_quota_state(self) -> None:
        """加载历史额度累计（day/week/month）。"""
    
    def _save_quota_state(self) -> None:
        """持久化额度累计到 ~/.ai-rd-team/quota-history.jsonl。"""
    
    def _notify_action(self, action: BudgetAction) -> None:
        """触发 Hook + 写 events.jsonl。"""
    
    def _avg_team_size(self) -> int:
        """粗略估算团队大小，用于广播成本计算。"""
        return max(self._snapshot.member_spawn_count, 1)
```

---

## 4. smart_pause 智能暂停

### 4.1 触发条件

- 资源点达到档位上限
- 任一资源维度硬限触达（members / messages / runtime_minutes 等）
- 单次预算 100% 用完且 model_fallback 已触发过仍不够

### 4.2 暂停流程

```python
def trigger_smart_pause(engine: "TeamEnvironmentManager", reason: str) -> None:
    """smart_pause 的完整流程。"""
    
    # 1. 暂停所有成员（不杀，只是不再派新消息）
    engine.pause_run(reason=f"budget: {reason}")
    
    # 2. 冻结当前 state，保存现场
    engine.runtime_state.freeze_current()
    
    # 3. 展示选择菜单（CLI 或 Web）
    choice = prompt_user({
        "prompt": "已达到资源上限，请选择",
        "options": [
            ("add_budget", "追加预算继续（推荐）", "ask_amount"),
            ("switch_model", "切换到便宜模型继续（需手工切换 CodeBuddy 模型）", None),
            ("keep_core", "仅保留关键角色（释放次要角色）", None),
            ("save_pause", "保存现场并暂停（稍后可恢复）", None),
            ("abandon", "放弃本次运行", "confirm"),
        ],
    })
    
    # 4. 根据选择执行
    if choice == "add_budget":
        amount = prompt_amount()
        engine.cost_tracker.expand_budget(amount)
        engine.resume_run()
    elif choice == "switch_model":
        display_instruction("请在 CodeBuddy 右上角切换到 claude-haiku")
        wait_user_confirm()
        engine.cost_tracker.mark_model_switched()
        engine.resume_run()
    elif choice == "keep_core":
        engine.drop_non_critical_members()  # 释放 tester / reviewer 等
        engine.resume_run()
    elif choice == "save_pause":
        # 已经 freeze，直接返回
        pass
    elif choice == "abandon":
        engine.stop_run(reason="user_abandoned_on_budget")
```

### 4.3 prompt_user 的实现

**CLI 场景**：标准输入读取  
**Web 场景**：写入 `runtime/commands/prompt-budget.json`，前端弹窗展示，用户点击后写回响应文件

---

## 5. 模型降级机制

### 5.1 触发

- 默认阈值 75%（`trigger_threshold: 0.75`）
- `model_fallback.enabled=true` 时才生效

### 5.2 第一期（CodeBuddy，semi_auto）

**流程**：

```
达到 75% → CostTracker 写 events.jsonl { event: "fallback_suggested" }
    ↓
FileWatcher 监听到 → HookRunner 触发 "fallback_suggested" hook
    ↓
内置 hook 推送通知到 Web 面板
    ↓
Web 面板弹窗：
    ┌────────────────────────────────────────┐
    │ 💰 预算 75% (¥15 / ¥20)                │
    │                                         │
    │ 建议切换到便宜模型继续：                  │
    │ 1. 在 CodeBuddy 右上角切换到 claude-haiku│
    │ 2. 点击下方按钮确认                      │
    │                                         │
    │ [已切换，恢复运行] [继续当前模型] [暂停]  │
    └────────────────────────────────────────┘
    ↓
用户切换模型 + 点击按钮
    ↓
前端 POST /api/cost/model-switched
    ↓
CostTracker.mark_model_switched() 写入 `runtime/cost/model-history.jsonl`
    ↓
引擎继续运行
```

**关键点**：第一期**不自动切换**任何东西，只负责"引导 + 记录"。

### 5.3 第二期（Full auto）

**启用条件**（满足任一）：
- CodeBuddy 开放工具级模型 API
- 使用支持运行时切换的 Adapter（如直连 Claude API）
- Adapter 的 `capabilities.supports_runtime_model_switch = True`

**策略：hybrid**

```python
def execute_fallback(
    tracker: CostTracker,
    adapter: BaseAdapter,
    config: CostControlConfig,
) -> None:
    """hybrid 降级策略。"""
    
    role_priority = config.model_fallback.role_priority
    model_chain = config.model_fallback.model_chain
    
    # 阶段 1：按角色降级（低优先级先降）
    current_role_assignments = _current_member_models()
    for priority in sorted(set(role_priority.values())):
        roles_to_downgrade = [
            role for role, p in role_priority.items() if p == priority
        ]
        for role in roles_to_downgrade:
            for member in _members_by_role(role):
                current = current_role_assignments[member.member_id]
                next_model = _next_in_chain(current, model_chain)
                if next_model:
                    adapter.switch_member_model(member, next_model)
        # 降一级后检查预算
        if tracker.check_budget() == BudgetAction.CONTINUE:
            return
    
    # 阶段 2：级联全员降级
    for model in model_chain[1:]:
        for member in all_members:
            adapter.switch_member_model(member, model)
        if tracker.check_budget() == BudgetAction.CONTINUE:
            return
    
    # 全部降到底仍不够，smart_pause
    trigger_smart_pause(engine, "even lowest model not enough")
```

### 5.4 role_models 第二期启用

第一期：`role_models.config` 仅记录意图，不实际生效。Adapter `capabilities.supports_role_specific_model=False`。

第二期：支持的 Adapter 在 `spawn_member` 时按 `role_models.config[role]` 传入对应模型。

---

## 6. 多币种与展示

### 6.1 计费模式

```python
class BillingMode(str, Enum):
    AUTO = "auto"                  # 首次启动询问
    SUBSCRIPTION = "subscription"  # 订阅制（只看 RP，不显示金额）
    RESOURCE_UNITS = "resource_units"  # 资源单位（默认推荐）
    ESTIMATED_COST = "estimated_cost"  # 金额预估（需 pricing.yaml）
    CENTRAL_QUOTA = "central_quota"    # 企业集中额度（第二期）
```

### 6.2 货币转换

```python
# ai_rd_team/cost/pricing.py

class Pricing:
    def __init__(self, pricing_file: Path):
        self._data = yaml.safe_load(pricing_file.read_text())
    
    def estimate_cost(
        self,
        tokens_input: int,
        tokens_output: int,
        model: str,
        currency: str = "auto",
    ) -> float:
        """估算金额。
        
        若 currency == "auto"，按 locale 判断（zh_* → CNY，其他 → USD）。
        """
    
    def rp_to_cost(self, rp: int, model: str, currency: str = "auto") -> float:
        """从 Resource Points 估算金额。100 RP ≈ 10000 tokens 对应模型的定价。"""
    
    def fx_convert(self, amount: float, from_: str, to: str) -> float:
        """币种换算（使用 pricing.yaml 的 fx_rate）。"""
```

### 6.3 展示层

Web 面板根据 `billing_mode` 和 `display_currency` 决定如何展示：

| billing_mode | 主展示 | 辅展示 |
|-------------|-------|-------|
| `subscription` | RP 进度条 | （无金额） |
| `resource_units` | RP 进度条 | （无金额） |
| `estimated_cost` | ¥ X.XX | RP 小字 |
| `central_quota` | 企业剩余额度 | RP 本次占用 |

---

## 7. 事后记录与权重校准

### 7.1 post-run.jsonl 格式

```jsonl
{"run_id":"abc1234","ended_at":"2026-05-04T18:00:00Z","mode":"standard","rp_used":385,"members_spawned":5,"messages":87,"minutes":62,"iterations":8,"actual_tokens_reported":31200,"actual_cost_reported_cny":0.66,"user_satisfaction":"good","notes":"略超预算但结果满意"}
```

### 7.2 校准建议算法

```python
def suggest_calibrated_weights(history: list[dict]) -> "ResourcePointWeights":
    """基于历史数据校准权重。
    
    做法：
    1. 过滤 actual_tokens_reported 存在的记录（至少 5 条）
    2. 对每条记录，计算"每项贡献"：
       - members_spawned × 权重_a
       - messages × 权重_b
       - minutes × 权重_c
       - iterations × 权重_d
       总和应 ≈ actual_tokens_reported / 100  (因为 100 tokens ≈ 1 RP)
    3. 最小二乘法求解 {a, b, c, d}
    4. 输出建议权重（可 ±20% 范围）
    """
```

### 7.3 权重热更新

- CostTracker 支持从 `runtime/cost/weights-override.yaml` 读取用户覆盖权重
- 每次 `start_run` 重新加载
- Web 面板提供"应用校准建议"按钮，写入 override 文件

---

## 8. 时间窗口额度实现

### 8.1 存储

```
~/.ai-rd-team/quota-history.jsonl

{"ts":"2026-05-04T10:00:00Z","run_id":"abc","rp":385}
{"ts":"2026-05-04T15:30:00Z","run_id":"def","rp":120}
...
```

### 8.2 统计查询

```python
def get_used_in_window(
    storage: Path,
    window: Literal["day", "week", "month"],
    now: datetime,
) -> int:
    """统计当前窗口内已用 RP。"""
    from_ts = _window_start(window, now)
    total = 0
    with storage.open() as f:
        for line in f:
            record = json.loads(line)
            if datetime.fromisoformat(record["ts"]) >= from_ts:
                total += record["rp"]
    return total
```

### 8.3 触发动作

```python
ACTIONS = {
    "smart_pause": lambda engine: trigger_smart_pause(engine, "quota"),
    "block_new_run": lambda engine: engine.block_new_run_today(),
    "warn_and_block": lambda engine: engine.block_and_warn_user(),
    "block_and_report": lambda engine: engine.block_and_generate_report(),
}

def enforce_quota(config: CostControlConfig, tracker: CostTracker, engine) -> None:
    for window in ("day", "week", "month"):
        used = get_used_in_window(config.quota.storage, window, datetime.now())
        limit = getattr(config.quota.windows, f"per_{window}")
        if used >= limit:
            action_name = getattr(config.quota.on_exceed, f"per_{window}")
            ACTIONS[action_name](engine)
            break
```

---

## 9. Hook 集成

CostTracker 触发以下 Hook：

| Hook | 何时 | 用途 |
|------|-----|------|
| `budget_threshold_reached` | 达到 75% 阈值 | 提示降级 |
| `budget_exceeded` | 达到 100% | 触发 smart_pause |
| `quota_day_warning` | 日额度达 80% | 提示用户 |
| `quota_day_blocked` | 日额度超限 | 禁止新运行 |
| `model_fallback_suggested` | 建议切换模型 | Web 弹窗 |
| `model_switched` | 用户确认已切 | 记录 + 恢复运行 |
| `cost_snapshot_updated` | 每次事件 | Web 实时展示 |

---

## 10. 配置联动（与 10-config-schema §3.11 的关系）

### 10.1 Basic 层 → Advanced 展开

`config.yaml`（Basic）：

```yaml
run_mode: standard
budget:
  per_run: 400
  per_day: 2000
```

→ 展开为 `EffectiveConfig.cost_control`：

```yaml
cost_control:
  default_mode: standard
  budget_standard:
    max_resource_points: 400     # 来自 budget.per_run
    max_members: 5                # 保留 preset 默认
    max_messages: 150
    max_broadcasts: 3
    max_runtime_minutes: 120
    max_total_iterations: 15
  quota:
    windows:
      per_run: 400
      per_day: 2000                # 来自 budget.per_day
      per_week: 10000              # 保留默认
      per_month: 30000             # 保留默认
```

### 10.2 不在 Basic 中的参数

- `resource_point_weights`：用权重 v1 默认
- `model_fallback.*`：默认 enabled + threshold=0.75 + hybrid
- `post_run_recording.enabled`：默认 true

用户需要调这些时走 `ai-rd-team config advanced`。

---

## 11. 验收标准

- ✅ CostTracker 实时计量 5 类事件
- ✅ RP 权重采用 P5 校准 v1 值
- ✅ 档位预算：Lite=120 / Standard=400 / Full=1500
- ✅ smart_pause 5 选项可用（CLI + Web）
- ✅ 模型降级第一期 semi_auto 流程跑通（事件 → 通知 → 用户操作 → 记录）
- ✅ 多级窗口额度（日/周/月）统计正确
- ✅ post-run.jsonl 能积累数据
- ✅ 权重热更新（weights-override.yaml）生效
- ✅ Hook 触发符合 §9
- ✅ Basic 配置能正确展开到 Advanced
- ✅ 单元测试覆盖 ≥ 80%（事件记录 / 预算检查 / 窗口统计 / 校准算法）

---

## 12. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | 引擎调用 CostTracker.start_run / record_* / end_run |
| `02-adapter.md` | Adapter 触发 spawn/message 事件 → 引擎记录 |
| `04-web-panel.md` | Web 从 `runtime/cost/resource-points.yaml` 读实时状态 |
| `09-hooks-security.md` | budget_* 和 quota_* hook |
| `10-config-schema.md` | cost_control 全量配置定义 |
| `11-runtime-protocol.md` | `runtime/cost/` 目录结构 |

---

## 13. 附录：成本体验用户故事

### 13.1 新用户第一次使用（Standard 档）

```
$ ai-rd-team run "写个简单的博客"

📊 当前状态：
   档位：Standard
   单次预算：400 RP（¥8）
   日剩余：2000 RP
   
成员派发中...
[⚡ +40 RP] 派发 chen-architect
[⚡ +40 RP] 派发 lin-developer-1
[⚡ +40 RP] 派发 wang-reviewer
[⚡ +40 RP] 派发 zhao-tester

...

📊 运行中：
   已用：285 / 400 RP (71%) ███████░░░
   
...

🏁 运行完成：
   总消耗：368 RP
   制品：12 个
   耗时：42 分钟
   
是否需要记录一下真实消耗？(帮助系统校准权重)
> [y/N]
```

### 13.2 预算触达 75%

```
...

⚠️  [75% 预算告警] 已用 300 / 400 RP
   建议切换到便宜模型继续（需手工在 CodeBuddy 右上角切换）
   
   [1] 切换后恢复
   [2] 继续当前模型
   [3] 暂停
```

### 13.3 日额度耗尽

```
$ ai-rd-team run "再来一个需求"

❌ 今日额度已用完：2050 / 2000 RP
   明天 00:00 重置；若紧急可改 config.yaml 增加 budget.per_day
   
   运行历史今日：
   - 10:00  abc1234  standard  385 RP  "博客项目"
   - 14:30  def5678  standard  420 RP  "订单模块"
   - 17:00  ghi9012  standard  645 RP  "评论功能"
   - 20:00  jkl3456  standard  600 RP  "移动端"
```
