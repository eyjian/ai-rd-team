---
type: memory
layer: agent.d
author: manual
created: 2026-05-04
updated: 2026-05-04
tags: [tech-stack]
estimated_tokens: 120
---

# BlogAPI 技术栈

- **语言**：Go 1.21+
- **框架**：go-kratos v2
- **数据库**：PostgreSQL 15+（用 GORM 访问）
- **认证**：JWT（kratos middleware/auth/jwt）
- **proto**：protobuf + google.api.http（生成 HTTP + gRPC handler）
- **DI**：wire
- **测试**：`go test ./... -race -cover` + testcontainers-go

## 目录约定

遵循 Kratos 标准：`api/`（proto）→ `internal/service/`（协议层）→ `internal/biz/`（业务）→ `internal/data/`（存储）。

## 禁止

- 不在 biz 层 import gorm / kratos/transport
- 不在 service 写业务逻辑
- 不手写 HTTP handler（proto 生成）
- 不用全局变量
