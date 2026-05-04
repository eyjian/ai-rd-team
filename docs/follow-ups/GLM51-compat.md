# Follow-up：GLM-5.1 基线对比 E2E

> 状态：🔀 deferred from M5 tasks 6.4 / 6.5
> 原 change：`openspec/changes/archive/2026-05-04-reduce-bridge-burden/`（已归档）
> 拆分原因：M5 主体是"减负能力"，GLM 对比本质是"模型兼容性"，二者正交；且 GLM 对比阻塞外部条件（用户需在 CodeBuddy 侧切会话到 GLM-5.1），不阻塞 M5 归档。
> 不走 openspec change 体系：本任务零代码变更、无 spec delta，openspec schema 要求"至少一条 delta"，强行走反而造假。

## 背景

M5（`reduce-bridge-burden`）在 **Claude-Opus-4.7** 上完成真实 E2E 验证：

| 指标 | 结果 |
|------|------|
| 手动应答次数 | 7 次（M4 baseline 12 次，降幅 42%） |
| initialize 耗时 | 7 ms（M4 baseline ~38 s） |
| auto_responded 事件数 | 4 条（shutdown_request） |
| `go build ./...` | ✅ 通过 |
| 二进制大小 | 27.6 MB |
| pytest | 425 passed |

ai-rd-team 的核心主张之一是**"同一份代码在 CodeBuddy 切换底层模型时无需改动即可工作"**。为了验证该主张，需要在 GLM-5.1 上跑一次等效 E2E，产出对比报告。

## 目标

- 零代码变更前提下，在 GLM-5.1 跑通 `prototype/M4-example2-e2e/` Standard 档 blog-api E2E
- 产出 `prototype/M4-example2-e2e/VERIFIED-m5-glm.md` 对比 Claude 版 `VERIFIED-m5.md`
- 给出 GLM-5.1 作为 ai-rd-team 第一期"等价替代模型"的定位结论（推荐 / 需限制 / 不推荐）

## 前置条件

1. CodeBuddy IDE 侧可切换主 Agent 模型至 GLM-5.1
2. 操作者能新开独立会话（与 Claude 版 session 隔离）
3. 仓库位于 `main` 分支，`git status` clean，HEAD 是 M5 归档后的 commit

## 步骤

### 1. 切换模型与新会话
- CodeBuddy 设置 → 模型 → 选 GLM-5.1
- 新开会话，交叉验证当前模型（可问"你使用的是什么模型"）

### 2. 清理 prototype
```bash
cd prototype/M4-example2-e2e
rm -rf .ai-rd-team/ quota-home/ driver.log driver.stdout.log driver.pid
```

### 3. 跑 E2E
```bash
python3 driver.py
```
按照 `VERIFIED-m5.md` §主 Agent 手动应答清单 节奏应答 7 类 intent：
- `team_create` × 1
- `task` × 4（architect / dev_1 / dev_2 / tester）
- `send_message type=message` × 1
- `team_delete` × 1

### 4. 采集数据
- `runtime/events.jsonl` → 统计 `bridge_auto_responded` 条数（预期 ≥ 4）
- `runtime/cost-summary.yaml` → 总 RP
- `runtime/artifacts/` → 文件数
- `cd runtime/artifacts/<project> && go mod tidy && go build ./... && go vet ./...`

### 5. 撰写报告 `VERIFIED-m5-glm.md`
四章节：
1. **基础数据对比表**（模型 / run_id / 用时 / 总 RP / 文件数 / `go build` / 手动应答 / auto_responded）
2. **协作质量观察**（architect 分工、dev_1↔dev_2 接口、tester 闭环）
3. **工具调用稳定性**（team_create / task / send_message 参数格式；malformed 案例）
4. **结论**（GLM-5.1 定位 + M6 候选 issue）

### 6. 更新 CHANGELOG
在 `[Unreleased]` 节 Verified 类别追加一行：
```
- Verified: GLM-5.1 on blog-api Standard (YYYY-MM-DD): <N> 次手动应答 / `go build` <pass|fail>
```

### 7. Commit + push
```bash
git add prototype/M4-example2-e2e/VERIFIED-m5-glm.md CHANGELOG.md
git commit -m "verify-glm51-compat: GLM-5.1 baseline E2E on blog-api"
git push
```

### 8. 完成后删除本文档
本文档仅为 follow-up 占位，任务完成后可删除或把内容合并到 VERIFIED-m5-glm.md。

## 验收

- [ ] 报告存在且含 4 章节
- [ ] 数据来自真实 run（run_id 可追溯）
- [ ] CHANGELOG 已更新
- [ ] 若 GLM 版 `go build` 失败，报告内含根因分析（prompt 理解 / 工具调用格式 / 协作断裂）
- [ ] 结论段明确 GLM-5.1 的推荐场景
