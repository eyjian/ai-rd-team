# 07 · 产出物落位（M7 新）

> 本文说明 ai-rd-team 跑完后**产物放在哪、为什么放在那、如何自定义**。
> 设计依据：`openspec/specs/design/07-artifacts.md §4`。

---

## 核心原则：交付物 vs 过程数据

ai-rd-team 把团队产出分成**两类**，分别放**两个地方**：

### 1. 交付物（delivery）→ **项目根**

团队真正要交付给你的东西：
- **代码**：`<module>/main.go`、`src/app.py` 等（由架构师选的技术栈决定）
- **文档**：`docs/requirements/REQUIREMENTS.md`、`docs/design/ARCHITECTURE.md` 等
- **测试**：`tests/test_xxx.py`（Python/JS）或与代码同目录的 `xxx_test.go`（Go）
- **部署脚本**：`Dockerfile`、`docker-compose.yaml` 在根目录；`deploy/k8s-xxx.yaml` 在子目录

**直接写在项目根下**，和你用 `git init` 正常管理的项目结构完全一致。

### 2. 过程数据（process）→ `.ai-rd-team/runtime/`

团队工作的"痕迹"：
- **评审**：`runtime/review/spec-review-xxx.md`
- **阶段报告**：`runtime/reports/report-phase-dev.md`、`report-run-summary.md`
- **状态**：`runtime/state/members/*.yaml`
- **日志**：`runtime/events.jsonl`、`runtime/logs/engine.log`
- **成本**：`runtime/cost/resource-points.yaml`

**这些不会污染你的项目根**。你想做产品分发时，`.ai-rd-team/` 可以直接忽略。

### 权威索引

`<project_root>/.ai-rd-team/runtime/manifest.yaml` 记录所有产出的索引（含 delivery + process）：

```yaml
artifacts:
  - path: "mysh/main.go"
    kind: code
    category: delivery         # 相对项目根
    producer: developer_1
  - path: "docs/design/ARCHITECTURE.md"
    kind: doc
    category: delivery
    producer: architect
  - path: "review/spec-review-user.md"
    kind: review
    category: process          # 相对 runtime_dir
    producer: reviewer
```

---

## 完整目录示例

架构师选了 Go + Kratos 技术栈，项目有 `mysh` 和 `mysqler` 两个模块：

```
~/my-project/                       # 项目根（你 git init 的地方）
├── mysh/                           # 代码模块（架构师决定）
│   ├── main.go
│   └── main_test.go                # Go 风格：测试同目录
├── mysqler/
│   ├── main.go
│   └── main_test.go
├── docs/
│   ├── design/
│   │   ├── ARCHITECTURE.md         # 架构师写
│   │   └── data-interfaces.yaml
│   ├── requirements/
│   │   └── REQUIREMENTS.md         # 需求分析师写
│   └── delivery/
│       └── checklist.md            # PM 维护的最终交付清单
├── deploy/
│   └── k8s-mysh.yaml
├── Dockerfile                      # 根级部署脚本
├── docker-compose.yaml
├── README.md                       # 项目自身 README（若有）
└── .ai-rd-team/
    ├── config.yaml
    ├── memory/                     # 团队记忆
    └── runtime/
        ├── manifest.yaml           # ← 权威索引
        ├── review/                 # reviewer 过程产出
        ├── reports/                # 阶段报告 + run 总结
        ├── state/                  # 成员状态
        ├── events.jsonl
        └── ...
```

---

## 架构师声明项目布局（可选）

框架内置 6 档默认布局（`python / go / js / vue3 / wechat-mp / fallback`），
大多数情况不用管——架构师开工后会自动从 memory 里的技术栈选型推断匹配的布局。

如果你（或架构师）想**显式声明**，写一份 `data-project-layout.yaml`：

```yaml
# <project_root>/.ai-rd-team/runtime/reports/data-project-layout.yaml
version: "1.0"
base: go                           # 继承 DEFAULT_LAYOUTS["go"]
overrides:
  code_dirs:                       # 项目根下的模块目录
    mysh: mysh
    mysqler: mysqler
  tests_mode: alongside            # separate（tests/ 下）或 alongside（代码旁）
  docs_root: docs                  # 文档根目录名
  # docs_subdirs:                  # 可选：自定义每个类别的子目录名
  #   design: arch                 # 例如把 design/ 改成 arch/
  deploy_root: deploy              # 部署产物子目录
  root_level_files:                # 允许直接落项目根的文件名白名单
    - Dockerfile
    - docker-compose.yaml
    - Makefile
```

### 加载优先级（高→低）

1. 架构师的 `data-project-layout.yaml`（运行时声明）
2. `config.advanced.yaml:artifacts.layout`（全局配置）
3. memory `agent.d/tech-stack-selected.md` 关键词推断（Go / Python / Vue 等）
4. `DEFAULT_LAYOUTS["fallback"]`（最后兜底：src/ + tests/）

解析结果会记录到 `runtime/events.jsonl` 的 `project_layout_resolved` 事件里，便于你确认。

---

## 升级指南：从 0.1.x 迁移到 0.2.x

如果你之前跑过 ai-rd-team 0.1.x，老的 `<workspace>/.ai-rd-team/runtime/artifacts/` 下可能还有产物。M7 后这套目录废弃，迁移最简单的方式：

```bash
# 1. 备份或确认老产物你已经不需要
mv <workspace>/.ai-rd-team/runtime/artifacts/ /tmp/old-ai-rd-team-artifacts/

# 2. 再跑一次团队，按新布局产出
ai-rd-team run "xxx"
```

我们**不提供**自动迁移 CLI（`ai-rd-team migrate` 不存在）——beta 期外部用户极少，手动清理 + 重跑成本最低。如将来真出现大量迁移需求，会通过 follow-up change 补这个命令。

---

## 常见问题

### Q: 我不想让代码落项目根，就想保留老行为？
A: 目前不支持。M7 之前的 `artifacts.code_output.strategy` 三档（`in_place` / `artifacts_only` / `both`）已删除。核心逻辑是："交付物直接进项目根" 是更合理的默认，如需评估阶段的"快照"可以用 git 分支或 archive 归档。

### Q: 架构师没写 `data-project-layout.yaml`，会用什么布局？
A: 按加载优先级走到 3（memory 推断）或 4（fallback）。memory 推断是读 `agent.d/tech-stack-selected.md` 做关键词匹配（`Go` / `Python` / `Vue` / `微信小程序` 等）。匹配不到就用 fallback = `src/ + tests/`。

### Q: 代码模块名和 `code_dirs` 里的 key 不匹配怎么办？
A: `write_code(module="foo", ...)` 若 `code_dirs` 里没有 `foo`，会**直接用 `foo` 作为目录名**（友好 fallback）。所以架构师即使没列全也不会报错，只是不能指定到非同名目录。

### Q: 老 API `recorder.write()` 调用还能用吗？
A: 不能。M7 直接删除了老方法（没保留 DeprecationWarning）。如果是你的自定义 Hook 或脚本调用了老 API，请改成新的 `write_code` / `write_doc` / `write_test` / `write_deploy` / `write_process` 五个方法之一。

---

## 相关文档

- 完整设计：`openspec/specs/design/07-artifacts.md`
- Spec 级契约：`openspec/specs/artifact-placement/spec.md`
- 本次变更记录：`openspec/changes/archive/*relocate-artifacts-to-root*/`
- 配置参考：[02-configuration.md](./02-configuration.md)
