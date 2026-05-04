# NEXT — 下次工作时从这里开始

> **用途**：session 交接的单一入口。下次任何人（或 AI session）继续这个项目时，**第一件事就是读这份文档**。
> **最后更新**：2026-05-04 22:45（M7 task 1-5 完成，E2E 验证 + 归档留给下次）
> **当前版本**：`0.2.0a1` alpha（已 bump；**本地产物未重建**，`dist/` 还是 0.1.0b1）
> **仓库状态**：`main` 分支 clean，四个 M7 commit 已同步到本地；**push 到 origin 尚未做**（等 E2E 过了再一起 push）

---

## 📋 新 session 起手式（照抄即可）

```bash
cd /data/workspace/github/eyjian/ai-rd-team

# 1. 状态自检（每次必跑）
git log --oneline -5                    # 最近 5 个 commit
git status --short                      # 有没有未提交
openspec list                           # 活跃 change
openspec list --specs 2>/dev/null       # 正式 spec
ls docs/follow-ups/ 2>/dev/null         # 阻塞的 follow-up

# 2. 读本文件（NEXT.md），按"进行中"段推进
```

## 🎯 项目状态速览（2026-05-04 22:45）

| 项 | 值 |
|---|---|
| 版本 | **`0.2.0a1`** alpha（已 bump，尚未发 PyPI；`dist/` 内仍是 0.1.0b1） |
| 已完成里程碑 | M1 + M2 + M3 + M4 + M5 + M6 |
| 进行中里程碑 | **M7**（`relocate-artifacts-to-root`，30/37 tasks = 81% 完成，仅剩 E2E 验证 + 归档） |
| 测试 | **494 passed** / coverage 稳定 / ruff 全绿 / openspec validate 通过 |
| 活跃 openspec change | **1**（`relocate-artifacts-to-root`） |
| 正式 spec | `adapter-bridge-auto-responder`（M5 归档产物） |
| PyPI | ❌ 未发布 |
| CodeBuddy marketplace | ✅ 已规范化（3 种安装方式都真机验证） |

---

## 🔄 进行中：M7 `relocate-artifacts-to-root`

### 已完成（4 个 commit）

```
c3476bb  M7 task 4+5: docs + Skills + examples + CHANGELOG (494 passed, 0.2.0a1)
44a2613  M7 task 2+3: ArtifactRecorder + Engine/Service wiring (494 passed)
e0495e5  M7 task 1: ProjectLayout data layer + tests (460 passed)
83fa67e  M7: propose relocate-artifacts-to-root (converged, 37 tasks)
```

- **核心设计落地**：代码/docs/tests/部署脚本 → 项目根；过程数据 → `.ai-rd-team/runtime/`
- **ArtifactRecorder 五方法**：`write_code` / `write_doc` / `write_test` / `write_deploy` / `write_process`
- **`ProjectLayout` 加载优先级**：架构师 yaml > config > memory 推断 > fallback（6 档默认）
- **manifest 语义**：提升到 `runtime/manifest.yaml`；entry 新增 `category: delivery|process` 字段
- **文本工程全部完成**：openspec 设计文档 / docs 用户手册 / 4 个 examples / SKILL.md / prompt 模板 / CHANGELOG / 版本号
- **老 API 硬切**：`write()` / `write_raw()` / `ArtifactRecorder(artifacts_dir=...)` 全部删除

### 剩余工作（7/37 tasks）

#### 6.x · E2E 真机验证 ⏳（0.5-1 天，需要"人 + AI 合作"）

> 核心问题：新路径走得通吗？架构师会不会写出 `data-project-layout.yaml`？代码真的落项目根吗？

- [ ] **6.1** 清空 `examples/02-blog-api/<workspace>/` 已有产物，跑一次 Standard 档 E2E
  - 验收：代码落到 `examples/02-blog-api/<workspace>/<module>/`（项目根）；`.ai-rd-team/runtime/manifest.yaml` 每条含 `category` 字段；`go build ./...` 通过
- [ ] **6.2** 跑 `pytest -q` + `ruff check .` + `ruff format --check .` 确认无回归
- [ ] **6.3** 写 `prototype/M7-relocate-e2e/VERIFIED.md`
  - 包含：新布局 `tree` 截图 / manifest 样例 / E2E 跑通证据 / 迁移指南验证（删 artifacts/ 重跑 OK）

**E2E 怎么跑**（给下次 session 的具体步骤）：
```bash
# 1. 清理老 workspace
rm -rf examples/02-blog-api/<workspace-name>/  # 具体名字看 examples/02-blog-api/ 里

# 2. 按 examples/02-blog-api/README.md 的说明启动
cd examples/02-blog-api
ai-rd-team run "..." --mode standard --no-onboarding

# 3. 新 session 的 AI 要扮演 bridge Skill 处理 intent：
#    ls .ai-rd-team/runtime/adapter-intents/
#    读每个 intent → 在 CodeBuddy 里调对应工具 → 写 result
#    （参考 plugins/ai-rd-team/skills/ai-rd-team-bridge/SKILL.md）

# 4. 盯着产物位置：
#    - tree <workspace> -L 2  （看代码是否在根、docs/ 是否存在）
#    - cat <workspace>/.ai-rd-team/runtime/manifest.yaml  （看 category 字段）

# 5. 集成测试（若 Go 项目）
cd <workspace>
go build ./...
go vet ./...
```

#### 7.x · 归档（0.5 小时）

- [ ] **7.1** `openspec archive relocate-artifacts-to-root`（全部 1-6 勾完后）
- [ ] **7.2** 更新 NEXT.md：标记 M7 完成，下推下一里程碑候选
- [ ] **7.3** 最终 commit + push
- [ ] **7.4** 可选：本地 `pip install dist/ai_rd_team-0.2.0a1-*.whl` 验证（需先 `python -m build`）；决定是否发 TestPyPI

### 如果 E2E 发现问题怎么办

可能的问题（按风险排序）：

1. **架构师没产出 `data-project-layout.yaml`** → 会 fallback 到 memory 推断或默认布局；不一定是 bug，但要确认推断结果合理
2. **成员按老路径 prompt 引导写入** → 说明 prompt 模板某处漏改；去 `src/ai_rd_team/roles/prompt.py` 搜 `artifacts/` 漏网
3. **代码真的落到 `runtime/artifacts/code/`** → 说明 `ArtifactRecorder.__init__` 或 `engine.manager` 还在用老逻辑；回看 commit `44a2613`
4. **manifest 条目没有 `category` 字段** → 说明 `_update_manifest` 没覆盖到某个路径；回看 `src/ai_rd_team/artifacts/recorder.py`

若问题小：直接改 + 补测试 + 纳入 M7 同一批
若问题大：拆 follow-up change（别阻塞 M7 归档）

---

## ⏸️ 暂停/待定决策

### D1 · 多平台 Adapter 方向（Trae / MCP / 自持 LLM）
- **现状**：调研完毕，发现 Trae 星型拓扑与 ai-rd-team P2P 协作主张冲突
- **三案**：A 受限 Trae（丢卖点）/ B MCP Adapter 反向回调（非标技术不确定）/ C MCP + 自持 LLM（0.1→1.0 架构跃迁）
- **决策位置**：`openspec/specs/2026-05-04-multi-platform-brainstorming.md`
- **下一步**：用户想清楚方向后，用 `openspec-propose` skill 立新 change

### D2 · PyPI 发布时机
- **现状**：`~/.pypirc` 已配 TestPyPI / PyPI 两个 token
- **未发原因**：M7 BREAKING 变更未 E2E 验证；等 M7 归档后再考虑发 `0.2.0a1` 到 TestPyPI
- **执行命令**（真要发时）：
  ```bash
  python3 -m build                                       # 先重建（当前 dist/ 还是 0.1.0b1）
  python3 -m twine upload --repository testpypi dist/*
  git tag v0.2.0a1 && git push --tags
  ```
- **安全待办**：token 长期不用 → 到 pypi.org 网站 revoke

## 📌 阻塞外部条件的 Follow-up

### F1 · GLM-5.1 基线 E2E（阻塞：需切 CodeBuddy 模型）
- **跟踪**：`docs/follow-ups/GLM51-compat.md`
- **阻塞**：当前 CodeBuddy session 是 Claude-Opus-4.7，无法自切模型，需用户在 IDE 侧手动切到 GLM-5.1 会话执行
- **注意**：命令和采集数据路径已按 M7 新布局更新

---

## 🎯 M7 归档后的下一里程碑候选

按推荐优先级（比上一版略调整，因为 M7 改变了基础）：

| # | 候选 | 工作量 | 特点 |
|---|------|------|------|
| 1 | **A3 PyPI 正式发布** `0.2.0a1` | 1-2d | M7 后是合适时机，BREAKING 有了，让早期用户上手 |
| 2 | **B4 Skills 深化**（Go+Kratos / Vue3 / 微信小程序 SOP） | 3-5d | 配合 M7 新布局，架构师生成的 `data-project-layout.yaml` 可作 Skills 样本 |
| 3 | **B1 成本校准**（RP → Token → USD） | 3-4d | 企业用户价值高 |
| 4 | **D1 Full 档 E2E**（7 人真实跑） | 4-6d | 补 Known Limitation |
| 5 | **B2 Memory 升级**（向量检索） | 5-7d | 目前没用户痛点，过度工程风险 |

**明确避免**：
- Web 面板加制品编辑器（越界产品形态，应该让用户用自己的 IDE）
- Trae 受限 Adapter（见 D1，会丢 P2P 卖点）

## 🗑️ 小杂事

- `~/.pypirc`（权限 0600）有 TestPyPI + PyPI token，长期不发 → 去网站 revoke
- `dist/` 有 0.1.0b1 产物，M7 已 bump 到 0.2.0a1，发布时需重建
- `prototype/M4-example2-e2e/quota-home/` / `driver.pid` 等 E2E 产物遗留，可选清理
- M7 新机制"架构师声明 `data-project-layout.yaml`"还未在真实 E2E 中触发验证；E2E 时重点观察

---

## 📚 关键文档索引

| 想看什么 | 在哪里 |
|---------|-------|
| 设计文档总入口 | `openspec/specs/design/ROADMAP.md`（M1-M7） |
| 12 份详细设计 | `openspec/specs/design/00..11.md`（07-artifacts 已按 M7 重写） |
| 归档的 M5 change | `openspec/changes/archive/2026-05-04-reduce-bridge-burden/` |
| **进行中的 M7 change** | `openspec/changes/relocate-artifacts-to-root/`（30/37 勾选完） |
| M7 用户手册 | `docs/07-artifact-placement.md` |
| 多平台方向暂停快照 | `openspec/specs/2026-05-04-multi-platform-brainstorming.md` |
| 用户手册 | `docs/01..07-*.md` + `docs/README.md`（入口） |
| 本次 alpha 变更 | `CHANGELOG.md` 的 `[Unreleased]` → M7 段（归档时 rename 为 `[0.2.0a1]`） |
| 发布流程 | `RELEASING.md` |

---

## 📝 session 收工 checklist（给未来的自己）

每次 session 结束前，按顺序做：

- [x] 确认所有改动已 commit（`git status --short` → 空）✅
- [x] 若有活跃 openspec change 进度变化，同步 tasks.md 勾选框 ✅（30/37 勾完）
- [x] 更新本文件（NEXT.md）：顶部"最后更新"时间 + 三段内容（进行中 / 待定 / 下个候选）✅
- [ ] `git add NEXT.md openspec/.../tasks.md && git commit -m "next: ..."` 把交接状态一起推上去
- [ ] 跟用户口头确认"今天打住"

---

> 这份文档是"人 × AI"协作的交接合同。保持简洁、保持真实、保持更新。
