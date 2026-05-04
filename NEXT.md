# NEXT — 下次工作时从这里开始

> **用途**：session 交接的单一入口。下次任何人（或 AI session）继续这个项目时，**第一件事就是读这份文档**。
> **最后更新**：2026-05-04 18:45（扩写 getting-started 文档后）
> **当前版本**：`0.1.0b1` beta（本地可装，**未发 PyPI**）
> **仓库状态**：`main` 分支 clean，已同步 origin

---

## 📋 新 session 起手式（照抄即可）

```bash
cd /data/workspace/github/eyjian/ai-rd-team  # 或你的实际路径

# 1. 状态自检（每次必跑）
git log --oneline -5                    # 最近做了啥
git status --short                      # 有没有未提交
openspec list --json                    # 活跃 change
openspec list --specs                   # 正式 spec
ls docs/follow-ups/ 2>/dev/null         # 阻塞的 follow-up

# 2. 读本文件（NEXT.md），按"进行中的工作"或"下个里程碑候选"推进
```

## 🎯 项目状态速览（2026-05-04）

| 项 | 值 |
|---|---|
| 版本 | `0.1.0b1` beta |
| 已完成里程碑 | M1 + M2 + M3 + M4 + M5（5 个，全 E2E 真实验证） |
| 测试 | 425 passed / coverage 83% / ruff 全绿 |
| 活跃 openspec change | 0 |
| 正式 spec | `adapter-bridge-auto-responder`（M5 归档产物） |
| PyPI | ❌ 未发布（用户决定暂缓，先手工安装） |
| 本地产物 | `dist/ai_rd_team-0.1.0b1-{.whl,.tar.gz}`（git 忽略） |

---

## 🔄 进行中的工作

（无）

## ⏸️ 暂停/待定决策

### D1 · 多平台 Adapter 方向（Trae / MCP / 自持 LLM）
- **现状**：调研完毕，发现 Trae 星型拓扑与 ai-rd-team P2P 协作主张冲突
- **三案**：A 受限 Trae（丢卖点）/ B MCP Adapter 反向回调（非标技术不确定）/ C MCP + 自持 LLM（0.1→1.0 架构跃迁）
- **决策位置**：`openspec/specs/2026-05-04-multi-platform-brainstorming.md`
- **下一步**：用户想清楚方向后，用 `openspec-propose` skill 立新 change

### D2 · PyPI 发布时机
- **现状**：`~/.pypirc` 已配 TestPyPI / PyPI 两个 token，构建产物已验证可装
- **未发原因**：用户 2026-05-04 18:10 决定"先手工安装可用即可"
- **执行命令**（真要发时）：
  ```bash
  python3 -m twine upload --repository testpypi dist/*   # 先 TestPyPI
  python3 -m twine upload dist/*                          # 后 PyPI
  git tag v0.1.0b1 && git push --tags
  ```
- **安全待办**：如长期不发布，到 pypi.org / test.pypi.org 网站把 token revoke

## 📌 阻塞外部条件的 Follow-up

### F1 · GLM-5.1 基线 E2E（阻塞：需切 CodeBuddy 模型）
- **跟踪**：`docs/follow-ups/GLM51-compat.md`（含完整步骤）
- **阻塞**：当前 CodeBuddy session 是 Claude-Opus-4.7，无法自切模型，需用户在 IDE 侧手动切到 GLM-5.1 会话执行
- **预期产物**：`prototype/M4-example2-e2e/VERIFIED-m5-glm.md` 对比报告
- **不走 openspec change 体系**：零代码变更、无 spec delta

---

## 🎯 M6 候选方向（2026-05-04 讨论后未选）

按推荐优先级：

| # | 候选 | 工作量 | 特点 |
|---|------|------|------|
| 1 | **B4 Skills 深化 + D1 Full 档 E2E** 组合 | 7-8d | 补 2 个 Known Limitation；产物可喂 README |
| 2 | **A3 PyPI 正式发布** | 1-2d | 最快见效；需用户决心 |
| 3 | **B1 成本校准**（RP → Token → USD） | 3-4d | 单点闭环；企业用户价值高 |
| 4 | **B4 Skills 深化**（Go+Kratos / Vue3 / 微信小程序 SOP） | 3-5d | 内容工程；直接提升演示效果 |
| 5 | **D1 Full 档 E2E**（7 人真实跑） | 4-6d | 补 Known Limitation |
| 6 | **B2 Memory 升级**（向量检索 / 召回 / 去重） | 5-7d | 目前没用户痛点，过度工程风险 |

**明确避免**：
- Web 面板加制品编辑器（越界产品形态，应该让用户用自己的 IDE）
- Trae 受限 Adapter（见 D1，会丢 P2P 卖点）

## 🗑️ 小杂事

- `~/.pypirc`（权限 0600）有 TestPyPI + PyPI token，长期不发 → 去网站 revoke
- `dist/` 有 0.1.0b1 产物，git 忽略，你本机才有
- `prototype/M4-example2-e2e/quota-home/` / `driver.pid` 等 E2E 产物遗留，可选清理

---

## 📚 关键文档索引

| 想看什么 | 在哪里 |
|---------|-------|
| 设计文档总入口 | `openspec/specs/design/ROADMAP.md`（M1-M5 + 风险） |
| 12 份详细设计 | `openspec/specs/design/00..11.md` |
| 归档的 M5 change | `openspec/changes/archive/2026-05-04-reduce-bridge-burden/` |
| 多平台方向暂停快照 | `openspec/specs/2026-05-04-multi-platform-brainstorming.md` |
| 用户手册 | `docs/01..06-*.md` + `docs/README.md`（入口） |
| 本次 beta 变更 | `CHANGELOG.md` 的 `[0.1.0b1]` 段 |
| 发布流程 | `RELEASING.md` |

---

## 📝 session 收工 checklist（给未来的自己）

每次 session 结束前，按顺序做：

- [ ] 确认所有改动已 commit + push（`git status --short` → 空）
- [ ] 若有活跃 openspec change 进度变化，同步 tasks.md 勾选框
- [ ] 更新本文件（NEXT.md）：顶部"最后更新"时间 + 三段内容（进行中 / 待定 / 下个候选）
- [ ] `git add NEXT.md && git commit -m "next: ..."` 把交接状态一起推上去
- [ ] 跟用户口头确认"今天打住"

---

> 这份文档是"人 × AI"协作的交接合同。保持简洁、保持真实、保持更新。
