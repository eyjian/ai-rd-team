---
type: memory
layer: agent.d
author: manual
created: 2026-05-04
updated: 2026-05-04
tags: [tech-stack]
estimated_tokens: 90
---

# TodoMini 技术栈

- **原生微信小程序**（不用 uni-app / Taro）
- **无后端**：所有数据在 `wx.setStorageSync('todos', [...])`
- **测试**：services 层用 Node 环境 Jest（`jest --testEnvironment=node`）
- **样式**：rpx 单位，不用 px

## 架构原则

- 页面 = 4 文件（.js / .json / .wxml / .wxss）
- 业务逻辑**抽到 services/**，页面只做视图和事件转发
- 组件用 Component() 而不是 Page()
- wx.* API 一律 Promise 封装（utils/wx-promise.js）

## 目录约定

```
miniprogram/
├── app.js / app.json / app.wxss
├── pages/           # 页面（4 个）
├── components/      # 可复用组件（2 个）
├── services/        # 业务逻辑（todo-store.js）
└── utils/           # 工具函数
tests/               # Jest 单测（services/）
project.config.json  # 微信开发者工具配置
```
