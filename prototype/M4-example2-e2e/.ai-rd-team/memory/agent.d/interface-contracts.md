---
type: memory
layer: agent.d
author: manual
created: 2026-05-04
updated: 2026-05-04
tags: [contracts]
estimated_tokens: 300
---

# BlogAPI 接口契约（架构师参考）

## proto 结构建议

```
api/blog/v1/
├── user.proto
├── post.proto
├── comment.proto
└── common.proto    # 共享类型（PageRequest / PageReply / Tag 等）
```

## 关键 HTTP 映射

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /v1/users | 注册 |
| POST | /v1/auth/login | 登录 |
| GET | /v1/users/me | 当前用户 |
| POST | /v1/posts | 发文章（需登录） |
| GET | /v1/posts/:id | 单篇 |
| GET | /v1/posts?page&size&tag | 列表 |
| PUT | /v1/posts/:id | 更新（作者） |
| DELETE | /v1/posts/:id | 删除（作者） |
| POST | /v1/posts/:id/comments | 发评论 |
| GET | /v1/posts/:id/comments | 评论列表 |
| POST | /v1/posts/:id/like | 点赞 |
| DELETE | /v1/posts/:id/like | 取消赞 |

## 数据库 schema（参考，可调整）

```sql
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  nickname VARCHAR(50) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE posts (
  id BIGSERIAL PRIMARY KEY,
  author_id BIGINT NOT NULL REFERENCES users(id),
  title VARCHAR(200) NOT NULL,
  body_markdown TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  likes_count BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_posts_author ON posts(author_id);
CREATE INDEX idx_posts_tags ON posts USING gin(tags);

CREATE TABLE comments (
  id BIGSERIAL PRIMARY KEY,
  post_id BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  author_id BIGINT NOT NULL REFERENCES users(id),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_comments_post ON comments(post_id, created_at DESC);

CREATE TABLE post_likes (
  post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (post_id, user_id)
);
```

## 错误码

用 Kratos errors：

```go
errors.Unauthorized("USER_UNAUTHORIZED", "需要登录")
errors.NotFound("POST_NOT_FOUND", "文章不存在")
errors.Forbidden("POST_NOT_OWNED", "不能修改他人文章")
errors.BadRequest("INVALID_PASSWORD", "密码太短（至少 8 位）")
```

## 分层契约

- `biz.UserUsecase.Register(ctx, email, pwd, nick) (*User, error)`
- `biz.PostUsecase.Create(ctx, authorID, title, body, tags) (*Post, error)`
- `biz.PostUsecase.List(ctx, page, size, tag string) ([]*Post, int64, error)`
- `biz.PostUsecase.Like(ctx, postID, userID) error`（幂等）
