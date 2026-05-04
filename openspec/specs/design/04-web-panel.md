# ai-rd-team 详细设计 - 04 Web 面板

> 文档版本：v1.0
> 日期：2026-05-04
> 颗粒度：架构级
> 依赖：`00-overview.md`、`03-service-api.md`、`11-runtime-protocol.md`

---

## 1. 目的与范围

### 1.1 目的
定义 ai-rd-team 的本地 Web 监控面板。这是用户与运行中团队交互的**主要可视化入口**——查看进度、读制品、发消息、调配置、看成本。

### 1.2 核心理念
- **漂亮**（头脑风暴原始诉求）
- **零打扰**（用户不看也能跑）
- **实时**（通过 SSE 无刷新更新）
- **CDN 加载**（无构建步骤，直接 F5 就能用）

### 1.3 范围
- 页面结构与导航
- 核心组件设计
- 实时更新机制
- 无构建方案

### 1.4 非目标
- ❌ 后端 API 实现（见 `03-service-api.md`）
- ❌ 具体组件库定制（用现成库）
- ❌ SSR / Electron 封装

---

## 2. 技术选型

### 2.1 核心选型

| 组件 | 选型 | 来源 | 理由 |
|------|------|------|------|
| 框架 | Vue 3 | CDN | 轻量、上手快、无编译 |
| CSS | TailwindCSS | CDN（Play CDN） | 快速出漂亮 UI |
| 图表 | Chart.js | CDN | 成熟、支持动画 |
| 图表（架构图） | Mermaid.js | CDN | 原生支持 Markdown 内的 mermaid |
| Markdown | marked + highlight.js | CDN | 渲染制品文档 |
| 图标 | heroicons | CDN | 与 Tailwind 风格一致 |
| SSE | 浏览器原生 EventSource | - | 无需依赖 |

### 2.2 无构建部署

**单 HTML 文件 + 几个 js 文件**，F5 刷新即最新。部署架构：

```
ai_rd_team/web/
├── index.html              # 主入口（~200 行）
├── assets/
│   ├── app.js              # Vue 应用根
│   ├── stores/             # 状态管理（简化的 Vue reactive store）
│   ├── components/         # 各页面组件（.vue 模板通过 defineComponent 注册）
│   ├── api.js              # API 封装
│   ├── sse.js              # SSE 封装
│   └── utils.js
└── styles/
    └── custom.css          # 补充 Tailwind 不够的自定义样式
```

Flask 后端通过 `send_from_directory` 提供静态文件。

---

## 3. 页面布局

### 3.1 主框架

```
┌────────────────────────────────────────────────────────────────────┐
│ [Logo] ai-rd-team    [当前运行: abc123 · running · Standard]  [⚙] │
├──────────────┬─────────────────────────────────────────────────────┤
│              │                                                      │
│  侧边栏导航   │           主内容区                                    │
│              │                                                      │
│  - 总览       │                                                      │
│  - 团队       │                                                      │
│  - 消息流     │                                                      │
│  - 制品       │                                                      │
│  - 记忆       │                                                      │
│  - 成本       │                                                      │
│  - 配置       │                                                      │
│  - 历史       │                                                      │
│              │                                                      │
├──────────────┴─────────────────────────────────────────────────────┤
│  底部状态条：[成员状态]  [资源点: 285/400]  [消息: 87]  [连接: ●]   │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 页面清单

| 页面 | 路由 | 内容 |
|------|------|------|
| 总览 | `/` | 仪表板（进度/成本/最近事件） |
| 团队 | `/team` | 成员卡片（头像/状态/当前任务/最近消息） |
| 消息流 | `/messages` | 时间线式消息流，可过滤 |
| 制品 | `/artifacts` | 树形目录 + 详情预览（Markdown 渲染） |
| 记忆 | `/memory` | ADR 列表、agent.d、memory.d 浏览器 |
| 成本 | `/cost` | 实时图表、成本明细、事后记录 |
| 配置 | `/config` | Basic/Advanced 切换式表单 |
| 历史 | `/history` | 过往运行列表 + 详情 |

### 3.3 进入即启动页（关键）

首次打开 Web 面板时若检测到无当前运行：

```
┌────────────────────────────────────────────────────┐
│                                                     │
│        👋 欢迎使用 ai-rd-team                        │
│                                                     │
│        请输入你的需求：                               │
│        ┌──────────────────────────────────────┐     │
│        │                                      │     │
│        │                                      │     │
│        └──────────────────────────────────────┘     │
│                                                     │
│        运行档位：                                     │
│        ⦿ Lite     (120 RP)   小玩意                 │
│        ⊙ Standard (400 RP)   中等 ← 默认             │
│        ⊙ Full     (1500 RP)  复杂系统                │
│                                                     │
│        [启动团队]                                     │
│                                                     │
└────────────────────────────────────────────────────┘
```

---

## 4. 核心组件

### 4.1 总览（仪表板）

```
┌─────────────────────────────────────────────────────────────┐
│  项目：user-management-system                                │
│  状态：● Running  ·  已跑 35 分钟  ·  Standard 档             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────┐ ┌─────────────────────────┐                  │
│  │  成员状态  │ │  成本                   │                  │
│  │           │ │                         │                  │
│  │  5 / 5    │ │  ███████░░░ 71%        │                  │
│  │  ● 3 工作  │ │  285 / 400 RP          │                  │
│  │  ○ 2 空闲  │ │  约 ¥5.70              │                  │
│  └───────────┘ └─────────────────────────┘                  │
│                                                              │
│  ┌──────────────────────────────────────────────┐           │
│  │  最近事件（实时）                              │           │
│  │                                                │           │
│  │  10:35  林1号 产出 src/api/user.go            │           │
│  │  10:33  王1号 开始评审 user-module            │           │
│  │  10:30  陈架构 发消息给 林1号                  │           │
│  │  10:28  预算达到 75% 阈值                     │           │
│  │  ...                                           │           │
│  └──────────────────────────────────────────────┘           │
│                                                              │
│  [暂停] [升档到 Full] [保存并停止]                            │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 团队页（成员卡片）

每个成员一张卡片：

```
┌────────────────────────────┐
│  🧑 陈架构 (architect)      │
│  ● Working                  │
│                             │
│  当前：设计用户接口           │
│  进度：████████░░ 80%       │
│                             │
│  最近：                      │
│  - 产出 spec-architecture.md│
│  - → 林1号：接口就绪         │
│                             │
│  [发消息] [查看全部消息]      │
└────────────────────────────┘
```

卡片颜色随状态变：
- 🟢 working
- 🔵 waiting
- 🟡 idle
- ✅ done
- ❌ failed

### 4.3 消息流页

时间线布局：

```
──────[10:00:00]──────
┌─[main → architect]─────┐
│ 启动任务                │
└────────────────────────┘

──────[10:00:45]──────
┌─[architect → developer_1]──┐
│ 接口设计就绪，详见...        │
│ 📎 data-interfaces.yaml    │
└────────────────────────────┘

──────[10:01:10]──────
┌─[developer_1 → architect]──┐
│ 接口中 email 是否大小写敏感？│
└────────────────────────────┘
...
```

**过滤器**：按成员、按消息类型、按关键词、按时间范围

**用户介入**：底部有"向某成员发消息"输入框。

### 4.4 制品页

左树右预览布局：

```
┌──────────────────┬──────────────────────────────────────┐
│ artifacts/        │ spec-architecture.md                 │
│ ├─ design/        │ ───────────────────────────────────  │
│ │  ├─ spec-arch...│ # 架构方案                           │
│ │  ├─ data-int... │                                      │
│ │  └─ data-task...│ > 作者：陈架构                       │
│ ├─ code/          │ > 日期：2026-05-04                   │
│ │  ├─ user.go     │                                      │
│ │  └─ ...         │ ## 1. 背景                           │
│ ├─ test/          │ ...                                  │
│ │  └─ test_user.py│                                      │
│ ├─ review/        │ ```mermaid                           │
│ └─ reports/       │ sequenceDiagram                      │
│                   │ ...                                  │
│                   │ ```                                  │
│                   │ [Mermaid 渲染图]                      │
│                   │                                      │
│                   │ [复制] [下载] [在编辑器打开]          │
└──────────────────┴──────────────────────────────────────┘
```

**Markdown 渲染**：marked + highlight.js + mermaid.js（自动识别 \`\`\`mermaid 代码块渲染）。

### 4.5 记忆页

```
┌─────────────────────────────────────────────────────────┐
│ [ADR] [agent.d] [memory.d]                              │
├─────────────────────────────────────────────────────────┤
│ ADR 列表：                                                │
│                                                          │
│ ✅ 0001 后端技术栈选择 Go + Kratos                       │
│    陈架构 · 2026-05-04 · accepted                       │
│                                                          │
│ ✅ 0002 移动端用微信小程序                                │
│    陈架构 · 2026-05-04 · accepted                       │
│                                                          │
│ ⏳ 0003 Redis 缓存策略                                    │
│    陈架构 · 2026-05-04 · proposed                       │
│                                                          │
│ [+ 新增 ADR] [导出所有]                                   │
└─────────────────────────────────────────────────────────┘
```

### 4.6 成本页

```
┌─────────────────────────────────────────────────────────┐
│  本次运行                                                 │
│  ┌──────────────────────────────┐                       │
│  │  ████████░░░░░ 285 / 400 RP │                       │
│  │  约 ¥5.70                   │                       │
│  └──────────────────────────────┘                       │
│                                                          │
│  消耗明细（饼图）：                                        │
│  ● 成员 spawn：200 RP (70%)                             │
│  ● 消息：80 RP (22%)                                    │
│  ● 运行时长：45 RP (16%)                                │
│  ● 迭代：60 RP (22%)                                    │
│                                                          │
│  额度追踪：                                               │
│  日：  ████████░░ 1200 / 2000 RP                        │
│  周：  ██░░░░░░░░ 4500 / 10000 RP                       │
│  月：  ██████░░░░ 18000 / 30000 RP                      │
│                                                          │
│  历史运行（柱状图，最近 10 次）                             │
│  [图表]                                                   │
└─────────────────────────────────────────────────────────┘
```

### 4.7 配置页（基础/高级切换）

```
┌─────────────────────────────────────────────────────────┐
│ [基础配置] [高级配置] [查看来源]                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  基础配置（config.yaml，自动生成）                         │
│                                                          │
│  项目描述    [实现一个用户管理模块            ]           │
│                                                          │
│  运行档位    ( ) Lite  (•) Standard  ( ) Full            │
│                                                          │
│  技术栈                                                   │
│    后端      [ Go + Kratos ▼ ]                          │
│    前端      [ Vue 3 ▼ ]                                │
│    移动端    [ 微信小程序 ▼ ]                            │
│                                                          │
│  预算                                                     │
│    单次      [ 400 ] RP                                  │
│    日上限    [ 2000 ] RP                                 │
│                                                          │
│  [保存] [恢复默认]                                        │
│                                                          │
│  💡 高级配置（模型降级/安全/Hook/日志等）                 │
│     默认不可见，点击上方"高级配置"Tab 查看                │
└─────────────────────────────────────────────────────────┘
```

### 4.8 历史页

```
┌─────────────────────────────────────────────────────────┐
│  运行历史                                                 │
│                                                          │
│  2026-05-04  abc12345  ✅ Standard  385 RP  "博客项目"  │
│  2026-05-03  def67890  ✅ Lite     105 RP  "Bug 修复"  │
│  2026-05-02  ghi11234  ❌ Standard 350 RP  "移动端"    │
│  ...                                                     │
│                                                          │
│  点击查看详情：制品 / 事件流 / 成本分布                    │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 实时更新

### 5.1 SSE 订阅策略

Web 面板连接三个 SSE 流：

| 流 | 更新什么 |
|----|---------|
| `/api/stream/events` | 全局事件（成员状态、消息、制品、Hook 触发） |
| `/api/stream/cost` | 实时成本快照（每 2 秒推一次，或有事件时推） |
| `/api/stream/member/{id}` | 仅查看某成员详情页时订阅 |

### 5.2 本地 Store

Vue 3 reactive：

```javascript
export const store = reactive({
  currentRun: null,
  members: {},        // {member_id: state}
  messages: [],       // 最近 N 条
  cost: null,
  lastEvent: null,
});

// SSE 订阅
const es = new EventSource('/api/stream/events');
es.addEventListener('member_status_changed', (e) => {
  const data = JSON.parse(e.data);
  store.members[data.member_id] = {...store.members[data.member_id], status: data.to};
});
es.addEventListener('artifact_written', (e) => {
  // 触发制品列表刷新
});
```

### 5.3 增量更新

- 消息流：追加新消息到列表头
- 制品：树形结构增量加节点
- 成员卡片：状态变化加过渡动画
- 成本进度条：数字平滑过渡

---

## 6. 用户操作（命令下发）

### 6.1 暂停 / 恢复 / 停止

顶部按钮 → POST `/api/run/pause`。

### 6.2 发消息给成员

团队页或消息流页底部输入框 → POST `/api/team/members/{id}/message`。

### 6.3 smart_pause 菜单

当收到 SSE `budget_exceeded` 事件时，弹出模态框：

```
┌────────────────────────────────────────┐
│  ⛔ 预算已用完                            │
│                                         │
│  当前进度：开发 80%，待评审 + 测试         │
│                                         │
│  ⦿ 追加预算继续（推荐）                   │
│    追加金额：[200] RP                   │
│                                         │
│  ⊙ 切换便宜模型（需手动在 CodeBuddy 切）  │
│  ⊙ 仅保留关键角色                        │
│  ⊙ 保存现场并暂停                        │
│  ⊙ 放弃本次运行                          │
│                                         │
│  [确认]  [取消]                          │
└────────────────────────────────────────┘
```

### 6.4 升档

配置页或顶部下拉菜单 → POST `/api/run/escalate`。

---

## 7. 视觉设计

### 7.1 配色

- 主色：Tailwind `indigo-600`
- 成功：`emerald-500`
- 警告：`amber-500`
- 危险：`rose-500`
- 背景：亮色 `slate-50`，暗色 `slate-900`

### 7.2 明暗模式

支持跟随系统 + 手动切换。持久化到 `localStorage`。

### 7.3 响应式

移动端（第一期非必须，但保证不崩）：
- 侧边栏变为抽屉
- 组件竖排

### 7.4 动画

- 数字变化：从旧值过渡到新值
- 成员状态变化：卡片轻微闪烁
- 新消息到达：从顶部滑入

---

## 8. 安全

### 8.1 XSS 防护

- Markdown 渲染用 marked + DOMPurify
- 用户输入不直接渲染成 HTML

### 8.2 路径校验

- 所有 `/api/artifacts/file?path=xxx` 请求由后端校验 path 是否在允许范围内（防路径穿越）

### 8.3 CSRF

第一期 API 设计上所有 mutation 都接受 POST JSON，不依赖 cookie，无 CSRF 风险。

---

## 9. 启动与访问

### 9.1 启动命令

```bash
$ ai-rd-team serve                    # 启动 Web
 * Running on http://127.0.0.1:8765
 
$ ai-rd-team serve --open             # 顺便打开浏览器
```

### 9.2 端口冲突

默认 8765 被占用时 → 递增试 8766/8767/...  
输出实际监听端口给用户。

### 9.3 不启动 Web 的模式

```bash
$ ai-rd-team run "需求" --no-web      # 纯 CLI 模式
```

---

## 10. 验收标准

- ✅ 8 个主页面按本文档结构实现
- ✅ 首次打开能直接输入需求启动团队
- ✅ SSE 实时更新稳定（成员状态 / 消息 / 成本）
- ✅ Markdown 制品能正确渲染（含 mermaid / 代码高亮）
- ✅ 配置页支持 Basic/Advanced 切换，保存生效
- ✅ 明暗模式切换
- ✅ smart_pause 模态框工作
- ✅ CDN 加载可用（无需本地编译）
- ✅ 端口冲突时自动递增

---

## 11. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `03-service-api.md` | 调用所有 `/api/*` 端点 |
| `10-config-schema.md` | 配置页用 Basic/Advanced 双视图 |
| `07-artifacts.md` | 制品页按 manifest 展示 |
| `06-memory-system.md` | 记忆页读写 memory/ |
| `08-cost-control.md` | 成本页读 resource-points.yaml |
| `11-runtime-protocol.md` | SSE 事件列表 |

---

## 12. 附录：示例 HTML 入口

```html
<!-- ai_rd_team/web/index.html -->
<!DOCTYPE html>
<html lang="zh" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ai-rd-team</title>
  <!-- TailwindCSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Vue 3 -->
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <!-- Mermaid -->
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <!-- Markdown -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
  <!-- highlight.js -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/styles/github-dark.min.css">
  <script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/highlight.min.js"></script>
  <link rel="stylesheet" href="/static/styles/custom.css">
</head>
<body class="h-full bg-slate-50 dark:bg-slate-900">
  <div id="app"></div>
  <script type="module" src="/static/assets/app.js"></script>
</body>
</html>
```
