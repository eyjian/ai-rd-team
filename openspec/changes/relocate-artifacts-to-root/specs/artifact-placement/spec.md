# Spec: artifact-placement

> Capability：明确 ai-rd-team 团队产出的"过程数据"与"交付物"语义分层及落位规则。
> 关联变更：`openspec/changes/relocate-artifacts-to-root/`
> 关联设计：`openspec/specs/design/07-artifacts.md §4`、`11-runtime-protocol.md §3`

## ADDED Requirements

### Requirement: 交付物 SHALL 落项目根，过程数据 SHALL 保留 `.ai-rd-team/` 下

代码 / 文档 / 测试 / 部署脚本 SHALL 直达项目根，具体子路径由 `ProjectLayout` 决定；评审 / 阶段报告 / manifest / 状态 / 日志 / 成本 / 消息 / adapter intent/result / memory / 归档 SHALL 保留 `<project_root>/.ai-rd-team/` 下。

#### Scenario: 代码写到 code_dirs 指定目录

- **WHEN** 成员调 `ArtifactRecorder.write_code(module="mysh", filename="main.go", content=..., producer="developer_1")` 且 `ProjectLayout.code_dirs["mysh"] == "mysh"`
- **THEN** 文件 SHALL 写入 `<project_root>/mysh/main.go`，manifest 新增 `{path: "mysh/main.go", kind: "code", category: "delivery", producer: "developer_1"}`

#### Scenario: 文档写到 docs 根下对应类别

- **WHEN** 成员调 `write_doc(category="design", filename="ARCHITECTURE.md", ...)`，`docs_root="docs"`，`docs_subdirs["design"]="design"`
- **THEN** 文件 SHALL 写入 `<project_root>/docs/design/ARCHITECTURE.md`，manifest 记 `{path: "docs/design/ARCHITECTURE.md", kind: "doc", category: "delivery"}`

#### Scenario: 非法 category 拒绝

- **WHEN** 调用 `write_doc(category="unknown", ...)`
- **THEN** SHALL 抛 `ValueError`，消息 MUST 列出合法集合 `{requirements, design, delivery, research}`；manifest MUST NOT 新增条目

#### Scenario: 测试按 tests_mode 路由（separate）

- **WHEN** `tests_mode="separate"`，`tests_root="tests"`，调 `write_test(module=None, filename="test_user.py", ...)`
- **THEN** 文件 SHALL 写入 `<project_root>/tests/test_user.py`

#### Scenario: 测试按 tests_mode 路由（alongside）

- **WHEN** `tests_mode="alongside"`，`code_dirs["mysh"]="mysh"`，调 `write_test(module="mysh", filename="user_test.go", ...)`
- **THEN** 文件 SHALL 写入 `<project_root>/mysh/user_test.go`

#### Scenario: alongside 模式缺 module 拒绝

- **WHEN** `tests_mode="alongside"` 但 `module=None`
- **THEN** SHALL 抛 `ValueError`，消息 MUST 含 "alongside mode requires module"

#### Scenario: 部署脚本按文件名惯例路由

- **WHEN** 调 `write_deploy(filename="Dockerfile", ...)` 且 `root_level_files` 含 `"Dockerfile"`
- **THEN** 文件 SHALL 写入 `<project_root>/Dockerfile`
- **WHEN** 调 `write_deploy(filename="k8s-user.yaml", ...)` 且不在 `root_level_files` 列表
- **THEN** 文件 SHALL 写入 `<project_root>/<deploy_root>/k8s-user.yaml`（默认 `deploy/`）

#### Scenario: 过程数据写到 runtime/<kind>/

- **WHEN** 调 `write_process(kind="review", name="spec-review-user", content=..., producer="reviewer", ext="md")`
- **THEN** 文件 SHALL 写入 `<project_root>/.ai-rd-team/runtime/review/spec-review-user.md`，manifest 记 `{path: "review/spec-review-user.md", kind: "review", category: "process"}`（path 相对 runtime_dir，含 kind 子目录前缀以便区分同名文件）

#### Scenario: 非法 kind 拒绝

- **WHEN** 调用 `write_process(kind="delivery", ...)`
- **THEN** SHALL 抛 `ValueError`，合法集合 `{review, report, log}`

### Requirement: manifest.yaml SHALL 在 runtime 根，path 语义二分

`manifest.yaml` 位置 SHALL 为 `<project_root>/.ai-rd-team/runtime/manifest.yaml`。`category=="delivery"` 的条目 `path` SHALL 为项目根相对；`category=="process"` 的条目 `path` SHALL 为 `runtime_dir` 相对。每条 entry MUST 含 `category` 字段，值 MUST ∈ `{"delivery", "process"}`。

#### Scenario: 交付物 path 为项目根相对

- **WHEN** `write_code(module="mysh", filename="main.go", ...)` 成功
- **THEN** manifest 新条目 MUST 满足 `path == "mysh/main.go"` 且 `category == "delivery"`

#### Scenario: 过程 path 为 runtime 相对

- **WHEN** `write_process(kind="report", name="report-phase-dev", ext="md", ...)` 成功
- **THEN** manifest 新条目 MUST 满足 `path == "report/report-phase-dev.md"`（含 kind 子目录前缀），`category == "process"`

#### Scenario: 老位置 manifest 触发迁移提示

- **WHEN** recorder 启动发现 `<runtime_dir>/artifacts/manifest.yaml` 存在、`<runtime_dir>/manifest.yaml` 不存在
- **THEN** SHALL 打印 warning 指引用户删除 `<runtime_dir>/artifacts/` 后重跑团队，以新位置为准，MUST NOT 读老文件

### Requirement: 框架 SHALL 提供 ProjectLayout 默认值并允许架构师覆盖

框架 SHALL 提供至少 6 档内置默认（`python / go / js / vue3 / wechat-mp / fallback`）。加载优先级 SHALL 为：(1) `<runtime_dir>/reports/data-project-layout.yaml`（架构师声明）；(2) `config.advanced.yaml:artifacts.layout`；(3) memory 中 `tech-stack-selected.md` 指向的默认；(4) `fallback`。

#### Scenario: 架构师 base + overrides 合并

- **WHEN** 架构师写 `data-project-layout.yaml` 为 `{version: "1.0", base: "go", overrides: {code_dirs: {mysh: "mysh"}, tests_mode: "alongside"}}`
- **THEN** `ProjectLayout.from_yaml(path)` 返回 layout MUST 满足：`tests_mode=="alongside"`（overrides）；`docs_root == DEFAULT_LAYOUTS["go"].docs_root`（base 继承）；`code_dirs == {"mysh": "mysh"}`（overrides 替换）

#### Scenario: 无架构师声明时从 tech-stack 推断

- **WHEN** 架构师 yaml 不存在，但 `memory/agent.d/tech-stack-selected.md` 记 `backend: go`
- **THEN** engine 加载的 layout MUST 等于 `DEFAULT_LAYOUTS["go"]`

#### Scenario: 所有来源失败时 fallback

- **WHEN** 架构师未声明、config 未指定、memory 无 tech-stack
- **THEN** layout MUST 等于 `DEFAULT_LAYOUTS["fallback"]`；`events.jsonl` SHALL 追加 `{event: "layout_fallback_used", reason: "no hints"}`

#### Scenario: yaml 格式错误不致命

- **WHEN** 架构师 yaml 字段拼错（如 `code_dir` 而非 `code_dirs`）导致校验失败
- **THEN** `from_yaml` SHALL 捕获并打 warning（含原因），返回 base（若有）或 fallback；MUST NOT 抛异常到 engine

### Requirement: ArtifactRecorder SHALL 通过 write_* 分派方法暴露落位规则

`ArtifactRecorder` SHALL 提供五个公共方法：`write_code` / `write_doc` / `write_test` / `write_deploy` / `write_process`，每个方法的语义落位见"交付物 vs 过程数据"Requirement 的各 Scenario。旧方法 `write()` / `write_raw()` SHALL NOT 存在（本 change 直接移除，不保留 DeprecationWarning 兼容层）。

#### Scenario: 构造签名必须提供 project_root / runtime_dir / layout

- **WHEN** 调用方构造 `ArtifactRecorder(project_root=..., runtime_dir=..., layout=...)`
- **THEN** 对象 SHALL 正常构造；若缺任一参数，SHALL 抛 `TypeError`（Python 位置参数机制）

#### Scenario: 老签名构造失败

- **WHEN** 调用方尝试 `ArtifactRecorder(artifacts_dir=some_path)`（老签名）
- **THEN** SHALL 抛 `TypeError`（关键字参数不匹配）；不存在兼容转发
