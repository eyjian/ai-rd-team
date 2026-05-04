# 角色与团队

## 7 个内置角色

| 角色 | display_name | 职责 | 可伸缩 | 默认 Skills |
|------|-------------|------|-------|------------|
| `pm` | 周立项 | 项目经理：协调、推进、风险管理 | ✗ | (无) |
| `analyst` | 沈需求 | 需求分析：从描述提炼核心价值 | ✗ | (无) |
| `architect` | 陈架构 | 架构设计：接口契约、模块解耦 | ✗ | code-review-checklist |
| `developer` | 林 | 开发：按契约实现代码 | ✓ (max 5) | python-best-practices, pytest-guide |
| `reviewer` | 王 | 代码检视：质量、风格、bug | ✓ (max 3) | code-review-checklist, python-best-practices |
| `tester` | 赵 | 测试：边界、异常、正常用例 | ✓ (max 3) | pytest-guide |
| `devops` | 钱 | DevOps：部署、CI/CD、环境 | ✗ | (无) |

## 三档默认组合

### Lite 档
```
developer × 1
```
小工具、demo、实验性功能。

### Standard 档
```
architect × 1
developer × 2   (可伸缩到 5)
tester × 1      (可伸缩到 3)
```
正经单模块项目，有接口设计 + 并行实现 + 专人测试。

### Full 档
```
pm × 1
analyst × 1
architect × 1
developer × 2    (可伸缩到 5)
reviewer × 1    (可伸缩到 3)
tester × 1      (可伸缩到 3)
devops × 1
```
大系统、多模块、需要完整流程。

## 可伸缩角色

`developer` / `reviewer` / `tester` 在 config.advanced.yaml 里可以调：

```yaml
roles:
  developer:
    default_instances: 3    # 默认创建多少个
    max_instances: 5        # 上限
```

调度规则（按档位 + 配置）：
- **Lite**：可伸缩角色限 1 个
- **Standard**：`min(default_instances, 2)`
- **Full**：按 `default_instances`

成员名约定：`developer` / `developer_2` / `developer_3`。

## 运行中升档（escalate_mode）

```python
# 通过 API
engine.escalate_mode("standard")

# 或通过 Web 面板
POST /api/run/escalate {"new_mode": "standard"}
```

只能**从低到高**：`lite → standard → full`。升档会自动对比当前成员和新档位默认 roster，缺哪个补哪个。

## 运行中加单个成员（add_member）

```python
engine.add_member("developer")            # 自动生成 developer_2
engine.add_member("tester", "tester_qa")  # 指定名字
```

或通过 API（尚未暴露，M5 计划）。

## Prompt 注入结构

每个成员 spawn 时收到的 Prompt 包含 6 段：

```
# 身份与职责
你是 林（developer）。persona...
团队成员：...
当前任务：...

# 工作目录
artifacts/ ... / state/members/developer.yaml

# 你要做什么（职责清单）
- xxx
- yyy

# 协作约束
✅ 允许：...
❌ 禁止：...

# Skills（可用技能）  ← 从 SkillsLoader 三层加载
## python-best-practices
...

# 记忆（背景知识）     ← 从 MemoryManager.load_agent_d
## 项目技术栈
...
```

典型 Prompt 长度：4000-5000 字。

## 自定义角色（Advanced）

```yaml
roles:
  security_expert:                       # 新增一个安全专家角色
    display_name: "李安全"
    persona: "你是安全专家，关注 OWASP Top 10，擅长代码安全审计和渗透测试。"
    scalable: false
    default_instances: 1
    max_instances: 1
    skills:
      - "code-review-checklist"
    memory_scope:
      agent_d: ["tech-stack-selected", "key-decisions"]
```

然后在 roster 里加上 `security_expert`：

```yaml
run:
  roster:
    - architect
    - developer
    - tester
    - security_expert    # 自定义角色
```

## 相关设计文档

- `openspec/specs/design/05-roles-skills.md` — 完整角色定义与 Skills 体系
- `openspec/specs/design/01-engine.md` — 引擎如何装配团队和成员
