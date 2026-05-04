做一个博客系统的后端 REST API，用 Go + Kratos 框架。

## 业务需求

### 用户
- 注册：POST /v1/users，body {email, password, nickname}；密码 bcrypt 哈希
- 登录：POST /v1/auth/login，body {email, password}，返回 JWT token（7 天过期）
- 获取自己信息：GET /v1/users/me，需要 Authorization: Bearer <token>

### 文章
- 发布：POST /v1/posts，body {title, body_markdown, tags}
- 查看单篇：GET /v1/posts/:id
- 列表分页：GET /v1/posts?page=1&size=10&tag=golang，返回 {posts, total, page, size}
- 更新：PUT /v1/posts/:id（仅作者）
- 删除：DELETE /v1/posts/:id（仅作者）

### 评论
- 发评论：POST /v1/posts/:id/comments，body {content}
- 列表：GET /v1/posts/:id/comments

### 点赞
- POST /v1/posts/:id/like 幂等加赞
- DELETE /v1/posts/:id/like 取消

## 技术栈

- Go 1.21+
- kratos v2（标准项目模板）
- GORM（PostgreSQL）
- JWT 用 kratos 的 middleware/auth/jwt
- proto 定义接口（不手写 handler）
- wire 做依赖注入
- testcontainers-go 跑集成测试

## 数据模型

```
users(id, email, password_hash, nickname, created_at, updated_at)
posts(id, author_id, title, body_markdown, tags[], likes_count, created_at, updated_at)
comments(id, post_id, author_id, content, created_at)
post_likes(post_id, user_id, created_at)   # 联合主键
```

## 非目标

- 不做前端
- 不做文章搜索（交给 ES，本期跳过）
- 不做邮件通知
- 不做图片上传

## 验收

- `go build ./...` 通过
- `go test ./... -race -cover` 通过，核心路径覆盖 ≥ 70%
- 能用 curl 完整跑一遍：注册→登录→发帖→评论→点赞
