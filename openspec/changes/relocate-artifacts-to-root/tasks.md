# Tasks: relocate-artifacts-to-root

> 总预算：~2-3 天（16-24 小时）。每项 ≤4 小时，含实现 + 测试 + 文档。
> 实现顺序：先 ProjectLayout 数据层（风险最低），再 Recorder 重构（核心），然后角色 Skills 文本，最后 examples / docs / E2E 验证。
> BREAKING：发布时 bump 到 0.2.0a1，CHANGELOG 明确标 BREAKING + 迁移指南（手动清理 + 重跑）。
> **与初版提案的差异（已收敛）**：不再提供 `ai-rd-team migrate` CLI；老 `write()` / `write_raw()` API 直接删除（不走 DeprecationWarning）。
>
> **进度（2026-05-04 22:45）**：30/37（81%）已完成。**剩余**：6.x（E2E 真机验证）+ 7.x（归档）。

## 1. ProjectLayout 数据层

- [x] 1.1 新建 `src/ai_rd_team/artifacts/layout.py`，定义 `ProjectLayout` dataclass（字段见 design.md D3）和 `DEFAULT_LAYOUTS` 表（python / go / js / vue3 / wechat-mp / fallback 六档）
  - **验收**：dataclass frozen=True；每个 DEFAULT 都能 `ProjectLayout(**d)` 构造通过；`code_dirs` / `docs_subdirs` 的 dict 默认值用 `field(default_factory=...)`；lint 过
- [x] 1.2 实现 `ProjectLayout.from_yaml(path: Path) -> ProjectLayout` + `ProjectLayout.from_memory(memory_mgr) -> ProjectLayout`
  - `from_yaml` 读架构师声明的 `data-project-layout.yaml`，支持 `base: <preset>` + `overrides: {...}` 两段合并
  - `from_memory` 读 memory 里的 `tech-stack-selected.md`，按 stack 挑 DEFAULT
  - **验收**：两个方法都有异常捕获，失败时返回 `DEFAULT_LAYOUTS["fallback"]` 并打 warning（log + events.jsonl）
- [x] 1.3 新测 `tests/unit/test_project_layout.py`
  - 覆盖：六档 DEFAULT 构造、from_yaml base+overrides 合并、from_yaml 字段错误 fallback、from_memory 匹配失败 fallback、layout 相等性
  - **验收**：≥ 10 个用例，全部通过

## 2. ArtifactRecorder 重构（硬切，无兼容层）

- [x] 2.1 改写 `src/ai_rd_team/artifacts/recorder.py`：
  - `__init__` 新签名 `(project_root, runtime_dir, layout)`，老签名 `(artifacts_dir)` **不保留**
  - `manifest_path` 从 `artifacts_dir/manifest.yaml` 改为 `runtime_dir/manifest.yaml`
  - `_update_manifest` 根据 `category` 字段选 base：`delivery` 用 `project_root`，`process` 用 `runtime_dir`；每条 entry 新增 `category` 字段
  - **验收**：新构造签名生效；老签名不存在；manifest 位置 + path 语义正确；lint 过
- [x] 2.2 新增 `write_code(module, filename, content, producer)` → `<project_root>/<layout.code_dirs[module]>/<filename>`
  - `module` 在 `layout.code_dirs` 不存在时，用 `module` 本身作为目录名（允许架构师没列全）
  - manifest 记 `category: "delivery"`, `kind: "code"`
  - **验收**：新单测 `test_write_code_honors_layout`、`test_write_code_fallback_module`
- [x] 2.3 新增 `write_doc(category, filename, content, producer)` → `<project_root>/<layout.docs_root>/<layout.docs_subdirs[category]>/<filename>`
  - `category` ∈ {"requirements", "design", "delivery", "research"}，非法值抛 `ValueError`
  - manifest 记 `category: "delivery"`, `kind: "doc"`
  - **验收**：新单测 `test_write_doc_four_categories`、`test_write_doc_invalid_category_raises`
- [x] 2.4 新增 `write_test(module, filename, content, producer)` → 按 `layout.tests_mode` 路由
  - `"separate"` + `module=None/any` → `<project_root>/<layout.tests_root>/<filename>`
  - `"alongside"` + `module="mysh"` → `<project_root>/<code_dir>/<filename>`（代码旁）
  - `"alongside"` + `module=None` → 抛 `ValueError("alongside mode requires module")`
  - **验收**：新单测 `test_write_test_separate_mode`、`test_write_test_alongside_mode`、`test_write_test_alongside_without_module_raises`
- [x] 2.5 新增 `write_deploy(filename, content, producer)` → 按文件名惯例落位
  - 根级文件列表（`layout.root_level_files`，默认 `["Dockerfile", "docker-compose.yaml", "docker-compose.yml", "README.md"]`）→ `<project_root>/<filename>`
  - 其它 → `<project_root>/<layout.deploy_root>/<filename>`
  - **验收**：新单测 `test_write_deploy_root_level`、`test_write_deploy_subdir`
- [x] 2.6 新增 `write_process(kind, name, content, producer, ext="md")` → `<runtime_dir>/<kind>/<name>.<ext>`
  - `kind` ∈ {"review", "report", "log"}，其它抛 `ValueError`
  - manifest 记 `category: "process"`
  - **验收**：新单测 `test_write_process_three_kinds`、`test_write_process_invalid_kind_raises`
- [x] 2.7 **删除**老 `write()` / `write_raw()` 方法 + 删除 `ARTIFACT_KINDS` 旧常量（若不再需要）
  - 同步清理/更新所有调用点：`tests/unit/test_runtime_and_artifacts.py`、`src/ai_rd_team/engine/manager.py`（若有）、`src/ai_rd_team/service/readers.py`（若有）
  - **验收**：`grep -r "recorder.write(" src/ tests/` 无命中旧签名；`grep -r "write_raw" src/ tests/` 无命中
- [x] 2.8 补齐 `tests/unit/test_recorder_layout.py`（新），覆盖四档 layout × 五类 write_* 的典型组合，确保 path 与 manifest 一致
  - **验收**：≥ 15 个组合用例全绿

## 3. Runtime / Engine / Prompt 接线

- [x] 3.1 改 `src/ai_rd_team/runtime/state.py`：`RuntimeState` 暴露 `project_root: Path` 字段（即 `workspace_dir`）
  - **验收**：`RuntimeState` 构造测试通过；无破坏现有字段
- [x] 3.2 改 `src/ai_rd_team/engine/manager.py::TeamEnvironmentManager.initialize()`：
  - 从 memory + `data-project-layout.yaml` 加载 `ProjectLayout`（用 `ProjectLayout.from_yaml` / `from_memory` 组合）
  - 把 layout 注入新构造的 `ArtifactRecorder(project_root=..., runtime_dir=..., layout=...)`
  - **验收**：新测 `test_manager_loads_layout_from_yaml`、`test_manager_fallback_layout_when_no_yaml`
- [x] 3.3 更新 `src/ai_rd_team/roles/prompt.py`：
  - 删除 `ROLE_TO_DIR`（被 `ArtifactRecorder.write_*` 接管）
  - 新增 `ROLE_TO_WRITE_METHOD` 映射：`{"analyst": "write_doc", "architect": "write_doc", "developer": "write_code", "tester": "write_test", "devops": "write_deploy", "reviewer": "write_process", "pm": "write_process"}`
  - **验收**：prompt 渲染测试（`tests/unit/test_prompt_renderer.py`）更新后全绿
- [x] 3.4 `src/ai_rd_team/service/readers.py` / `service/web/index.html`：面板展示制品时 path 语义更新为"项目根相对 / runtime 相对"（按 `category` 字段区分）
  - **验收**：`tests/integration/test_service_api.py` 中 `/api/artifacts` 端点断言更新后全绿

## 4. Skills / Prompt 文本更新

- [x] 4.1 更新 `plugins/ai-rd-team/skills/ai-rd-team-launcher/SKILL.md`：提到产出位置的段落改为"代码在项目根、文档在 docs/、过程在 .ai-rd-team/runtime/"
  - **验收**：md 通顺，示例路径统一
- [x] 4.2 更新各角色 Prompt 模板（`src/ai_rd_team/roles/templates/*.j2` 或等效位置）中的产出位置引导
  - architect：写到 `docs/design/`、`docs/requirements/`
  - developer：写到 `<module>/`（项目根）
  - tester：按 `layout.tests_mode` 写到 `tests/` 或 `<module>/`
  - devops：写到项目根 / `deploy/`
  - reviewer / pm：写到 `.ai-rd-team/runtime/review` / `runtime/reports`
  - **验收**：`tests/unit/test_prompt_renderer.py` 更新后全绿；人工读过一遍没错路径
- [x] 4.3 在 architect 角色 Skill 里补"层次决策 + `data-project-layout.yaml` 模板"段落（若用户选了主流栈可省略）
  - **验收**：模板含 base+overrides 示例；指向 07-artifacts.md 作为参考

## 5. 文档 / 示例 / CHANGELOG

- [x] 5.1 重写 `openspec/specs/design/07-artifacts.md`
  - §4.1 目录结构：拆"过程 / 交付"两块
  - §4.3：`in_place` 成为唯一策略（删除 both / artifacts_only），扩展到 code/doc/test/deploy 四类
  - §7.2：`ArtifactRecorder` 接口改为新 write_* 分派
  - §10 典型制品流：T1/T1+ 落到项目根（`mysh/main.go`），T2 落到 runtime/review
  - §13 速查表：全面更新"放哪"列
  - **验收**：`openspec validate --strict` 过；人工读一遍；链接不 broken
- [x] 5.2 更新 `openspec/specs/design/11-runtime-protocol.md`：`runtime/` 目录树去掉 artifacts/（移到项目根），加入 review/ reports/ manifest.yaml
  - **验收**：目录树与 07-artifacts 保持一致
- [x] 5.3 更新 `openspec/specs/design/05-roles-skills.md`：各角色 "产出主文件" 路径引导
- [x] 5.4 更新 `docs/01-getting-started.md`：第 6/7 步的产物路径截图 + 说明
- [x] 5.5 更新 `docs/02-configuration.md`：新增 `artifacts.layout` 配置段；删除老 `artifacts.code_output.strategy` 说明
- [x] 5.6 新增 `docs/07-artifact-placement.md`：一页说明"代码去哪 / 文档去哪 / 测试去哪 / 过程去哪 / 架构师如何声明 layout / 老 workspace 如何手动切换"
  - **验收**：md 通顺，和 07-artifacts 互补（07-artifacts 是设计，docs/07 是用户手册）
- [x] 5.7 更新 `examples/01-smart-bookmark/EXPECTED_OUTPUTS.md` + README
- [x] 5.8 更新 `examples/02-blog-api/EXPECTED_OUTPUTS.md` + README
- [x] 5.9 更新 `examples/03-todo-mini/EXPECTED_OUTPUTS.md` + README
- [x] 5.10 更新 `examples/04-custom-skill/EXPECTED_OUTPUTS.md` + README
- [x] 5.11 更新 `CHANGELOG.md` 的 `[Unreleased]` 节（最终作为 `[0.2.0a1]`）：
  - **BREAKING**: 交付物落位从 `.ai-rd-team/runtime/artifacts/` 迁移到项目根
  - Added: `ProjectLayout`、`ArtifactRecorder.write_{code,doc,test,deploy,process}`、`data-project-layout.yaml` 支持
  - Removed: `ArtifactRecorder.write()` / `write_raw()` 老接口（无 deprecated 过渡）
  - Changed: `manifest.yaml` 位置提升到 `runtime/`；path 字段语义改为项目根相对（delivery）或 runtime 相对（process）
  - Migration: 手动清理 `<workspace>/.ai-rd-team/runtime/artifacts/` 后重新运行团队；不提供自动迁移 CLI
  - **验收**：含四类变更 + 迁移指南段落，Keep a Changelog 风格
- [x] 5.12 更新 `pyproject.toml` 版本号 `0.1.0b1` → `0.2.0a1`；Classifier 从 `4 - Beta` 降级为 `3 - Alpha`
  - **验收**：`python -m build` 产出 `ai_rd_team-0.2.0a1-*.whl`

## 6. 真实 E2E 验证

- [ ] 6.1 清空 `examples/02-blog-api/` 下已有 workspace 产物，跑一次 Standard 档 E2E
  - **验收**：代码落到 `examples/02-blog-api/<workspace>/<module>/`（项目根），不再在 `.ai-rd-team/runtime/artifacts/code/`；manifest.yaml 在 `.ai-rd-team/runtime/manifest.yaml`；`go build ./...` 或相应 lang 的验证通过
- [ ] 6.2 跑 `pytest -q`、`ruff check .`、`ruff format --check .`
  - **验收**：exit=0；pytest 全绿（原 425 + 新增 ≥ 35）；ruff 全绿
- [ ] 6.3 产出 `prototype/M7-relocate-e2e/VERIFIED.md`，含：新布局截图（project root tree）、manifest 样例、example 02 跑通证据、迁移指南验证（清理后重跑 OK）
  - **验收**：报告含上述 4 块内容，数据真实

## 7. 归档 / 发布

- [ ] 7.1 确认 1-6 全部 `[x]`，执行 `openspec archive relocate-artifacts-to-root`
  - **验收**：`openspec/changes/archive/<date>-relocate-artifacts-to-root/` 存在；`specs/artifact-placement/spec.md` 成为正式 spec
- [ ] 7.2 更新 `NEXT.md`：标记 M7 完成，下一步候选下推一位
- [ ] 7.3 commit：`git commit -m "M7: relocate artifacts to project root (BREAKING, 0.2.0a1)"`
- [ ] 7.4 （可选）本地 `pip install dist/ai_rd_team-0.2.0a1-*.whl` 验证可装；决定是否发 TestPyPI
