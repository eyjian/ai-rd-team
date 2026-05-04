# Architect Report — BlogAPI

> 作者：陈架构（architect）
> 日期：2026-05-04
> 项目：M4-example2-e2e（BlogAPI / Go + Kratos v2）

## 一、阶段性产出（架构设计完成）

| 类别     | 路径                                                                     | 说明                                                     |
| -------- | ------------------------------------------------------------------------ | -------------------------------------------------------- |
| 架构文档 | `artifacts/docs/architecture.md`                                         | 分层、wire 图、中间件链、错误码、配置、分工、里程碑      |
| biz 契约 | `artifacts/docs/biz-contracts.md`                                        | biz 层 Usecase/Repo 接口骨架 + 错误映射表 + auth helper  |
| 接口契约 | `artifacts/code/api/blog/v1/user.proto`                                  | 注册 / 登录 / 获取 me                                    |
|          | `artifacts/code/api/blog/v1/post.proto`                                  | 文章 CRUD + 分页列表                                     |
|          | `artifacts/code/api/blog/v1/comment.proto`                               | 评论 + 点赞（幂等）                                      |
| 数据库   | `artifacts/code/configs/schema.sql`                                      | 4 张表 DDL，含 GIN/复合索引                              |

## 二、关键技术决策

1. **proto 优先**：所有 HTTP 路径通过 `google.api.http` 注解映射；不手写 handler。
2. **严格分层**：biz 不依赖 gorm/kratos/transport；Repo 接口在 biz 中，GORM 实现在 data；service 只做 DTO 转换。
3. **JWT**：HS256，`sub = user_id (string)`，TTL = 7 天；白名单路径在 HTTP 中间件中用 selector 排除。
4. **点赞幂等**：`INSERT ... ON CONFLICT DO NOTHING` + 事务内根据 RowsAffected 维护 `posts.likes_count`。
5. **哨兵错误 + 映射**：biz 层用 `ErrXxx`，service 层翻译成 `kratos/errors`（`USER_EMAIL_EXISTS / USER_CRED_INVALID / POST_NOT_FOUND / POST_NOT_OWNED` 等）。
6. **测试**：testcontainers-go 启 PostgreSQL 15 + 执行 `schema.sql`；biz 层用手写 fake repo 做单测。

## 三、分工（已发 send_message）

| 成员         | 范围                                                               |
| ------------ | ------------------------------------------------------------------ |
| developer_1  | `internal/biz/*`（3 个 Usecase + Repo 接口）+ `internal/data/*`（GORM 实现）+ biz 单测 |
| developer_2  | `go.mod / Makefile / api/*.pb.go 生成 / internal/conf/ / internal/service/ / internal/server/ / internal/pkg/auth / cmd/blog/ (main+wire)` |
| tester       | `tests/integration/*`（testcontainers-go 骨架 + 端到端用例 16 条）+ 覆盖率补齐 |

## 四、关键边界与约束

- module 名：`blog`（由 developer_2 初始化 go.mod 时确定）
- biz ↔ service 交互点：`biz-contracts.md`（dev 之间需先读）
- 配置：`internal/conf.Bootstrap { Server, Data, Auth }`，YAML 样例已在 architecture.md 第 9 节
- 验收命令：`go build ./...` / `go test ./... -race -cover`（核心路径 ≥ 70%）

## 五、下一步

- 等 developer_1 / developer_2 / tester 实现反馈
- 对 biz 接口签名变更、wire 装配问题进行 P2P review
- 全部 developer 完工后统一做一次架构 review，必要时补 review 文档
