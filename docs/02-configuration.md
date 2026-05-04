# 配置详解

ai-rd-team 有**两层配置**：Basic（99% 用户只需要这个）和 Advanced（高级用户可选）。

## Basic 层：`.ai-rd-team/config.yaml`

首次 `ai-rd-team init` 或 Web 面板引导会生成。5 个字段搞定：

```yaml
config_version: "1.0"

project:
  description: "一句话说项目是干嘛的（可选）"

run_mode: "standard"     # lite / standard / full

tech_stack:
  backend: null          # null = 架构师自主选；也可填 "go" / "python" / "nodejs"
  frontend: null         # 或 "vue3" / "react" / "svelte"
  mobile: null           # 或 "wechat-miniprogram" / "react-native" / "flutter"

budget:
  per_run: 400          # 单次运行 RP 预算
  per_day: 1500         # 每日额度
```

### 三档预算推荐

| 档位 | per_run | per_day | 适用场景 |
|------|---------|---------|---------|
| lite | 120 | 500 | 小玩意、demo、几天搞完 |
| standard | 400 | 1500 | 正经项目、单模块、几周迭代 |
| full | 1500 | 5000 | 大系统、多模块、长期演进 |

`ai-rd-team config preset --mode standard` 会导出完整配置到 `config.advanced.yaml`，你可以在此基础上微调。

### 运行时覆盖

```bash
# 临时切档位（不改 config.yaml）
ai-rd-team run --mode full "需求"

# 临时改预算
ai-rd-team run --budget 800 "需求"
```

## Advanced 层：`.ai-rd-team/config.advanced.yaml`（可选）

当你需要调优时才用。例如：

- 给特定角色指定 Skills
- 调整可伸缩角色的实例数
- 自定义 Hook
- 调整 RP 权重
- 配置模型降级链

```yaml
# 只覆盖你想改的字段，其他字段走 preset 默认值

roles:
  architect:
    skills:
      - "go-kratos-basics"
      - "code-review-checklist"
    memory_scope:
      agent_d:
        - "tech-stack"
        - "interface-contracts"
        - "key-decisions"
  developer:
    skills:
      - "go-kratos-basics"
    default_instances: 3
    max_instances: 5
  tester:
    default_instances: 2

cost_control:
  budget_standard:
    max_resource_points: 600    # 覆盖默认 400
  model_fallback:
    enabled: true
    trigger_threshold: 0.7       # 超 70% 预算就建议降级（默认 0.75）
    model_chain:
      - "claude-opus-4.7"
      - "claude-sonnet-4.7"
      - "claude-haiku-4.5"
  on_budget_exceeded: "smart_pause"  # 或 "stop" / "warn"

hooks:
  enabled: true
  custom:
    - name: "notify-feishu-on-stop"
      trigger: "run_stopped"
      priority: 100
      command: "python scripts/feishu.py --run $RUN_ID --reason $REASON"
      on_failure: "warn"

security:
  file_access:
    writable:
      - ".ai-rd-team/runtime/artifacts/"
    forbidden:
      - ".git/"
      - ".env"
```

## ConfigInference：自动填默认值

ai-rd-team 能从工作区自动推断：

- **项目名**：目录名（可手动覆盖）
- **描述**：`README.md` 的首个 `# 一级标题`
- **语言**：扫描 `pyproject.toml` / `go.mod` / `package.json` 等

首次 `init` 时会展示推断结果给你确认：

```
项目识别：python + pyproject.toml + README
默认档位：standard
推荐预算：400 RP/次
```

## 配置优先级

从高到低：

1. CLI 参数（`--mode`, `--budget`）
2. `config.advanced.yaml`
3. `config.yaml`（Basic 层 → 自动展开成 Advanced）
4. Preset 内置默认值（按 run_mode）
5. `ConfigInference` 推断值

## 校验配置

```bash
ai-rd-team config validate
```

会检查 schema 合法性、字段引用（Skills / Hook 命令是否存在）、路径可访问性等。

## 相关设计文档

- `openspec/specs/design/10-config-schema.md` — 完整 Schema 与字段说明
