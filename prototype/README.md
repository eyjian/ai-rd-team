# ai-rd-team 原型验证

> 日期：2026-05-03
> 状态：进行中
> 目的：在进入详细设计前，通过最小原型验证核心技术假设

---

## 原型目的

ai-rd-team 的设计基于几个关键技术假设。如果这些假设不成立，大量详细设计工作会白费。本原型用**最小可行实验 + 参考实现**的方式快速验证：

1. CodeBuddy Team 模式能否真正实现"自主驱动"（而非"main 转发式")
2. 多成员能否并发协作并正确产出制品
3. Web 面板与运行中 Team 的通信方案选型
4. Resource Points 权重的真实校准数据

---

## 工作方式（双路径）

每项实验采用**路径 C：真实实验 + 参考实现**并行：

| 路径 | 形式 | 产物 |
|------|------|------|
| **路径 A：真实实验** | 在当前 CodeBuddy IDE 会话中真实派发 Team 成员 | `results/` 下的观察日志、指标数据 |
| **路径 B：参考实现** | 独立 Python 脚本模拟机制 | `simulated/` 下的代码 |

路径 A 拿真实数据验证假设；路径 B 沉淀可复用代码作为未来实现参考。

---

## 实验场景

**小型代码开发**：3 角色协作实现一个 Python 计算器

- **architect**（架构师）：设计接口和数据结构
- **developer**（开发者）：实现代码
- **tester**（测试）：写单元测试并执行

**交付物**：
- `calculator.py`：四则运算函数实现
- `test_calculator.py`：pytest 单元测试
- `design-note.md`：架构师的简要设计说明

选这个场景的原因：
- 覆盖设计 → 开发 → 测试完整雏形
- 多角色并发写不同文件，能验证制品并发安全
- 体量小（~50K tokens 可完成），成本可控

---

## 验证项（P1-P5）

| # | 验证项 | 目标 | 位置 |
|---|--------|------|------|
| P1 | 基础 Team 协作 | CodeBuddy Team 模式能否支持自主驱动的多成员对话 | `01-basic-team/` |
| P2 | Skills 加载 | 成员能否正确加载并使用 Skills 目录中的技能 | `02-skills-loading/` |
| P3 | Web 面板通信 | Web 面板与运行中 Team 通信方案选型 | `03-web-bridge/` |
| P4 | 制品并发写 | 多成员并发写不同文件的安全性 | `04-artifacts/` |
| P5 | 成本基线 | 测量真实 token 消耗，校准 Resource Points 权重 | `05-cost-baseline/` |

详见 [VERIFICATION-PLAN.md](./VERIFICATION-PLAN.md)。

---

## 目录结构

```
prototype/
├── README.md                    # 本文件
├── VERIFICATION-PLAN.md         # 5 项验证详细计划
├── REPORT.md                    # 最终汇总报告（最后输出）
│
├── shared/                      # 共享工具
│   ├── token_counter.py
│   ├── metrics_collector.py
│   └── artifact_recorder.py
│
├── 01-basic-team/               # P1
│   ├── experiment.md
│   ├── simulated/               # 路径 B：Python 模拟
│   └── results/                 # 路径 A：真实实验
│
├── 02-skills-loading/           # P2
├── 03-web-bridge/               # P3
├── 04-artifacts/                # P4
└── 05-cost-baseline/            # P5
```

---

## 原型的边界（非目标）

- ❌ 不实现完整 Adapter（只验证关键机制）
- ❌ 不做 Web UI（只验证通信方案）
- ❌ 不实现全部 7 个固定角色（只用 3 个简化角色）
- ❌ 不做配置 Schema 完整实现（硬编码必要参数即可）
- ❌ 不做美化/错误处理（验证完即抛）
- ❌ 不是最终代码（未来详细设计阶段会重写）

---

## 成功判定

当全部 5 项实验得出结论（✅ 成立 / ❌ 不成立 / ⚠️ 有条件成立），并输出 `REPORT.md` 时，本原型完成。

**不要求所有假设都成立**——即使 P1 失败，也是有价值的输入（会改变整个架构方向）。
