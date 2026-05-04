-- BlogAPI PostgreSQL schema
-- Owner: architect
-- Target: PostgreSQL 15+
-- 使用方式：开发/测试环境由 developer_1 拷贝到 configs/schema.sql，
--           并在 testcontainers / docker 起库时 psql -f 执行一次。

BEGIN;

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  email         VARCHAR(255) NOT NULL UNIQUE,  -- 入库前 lower()
  password_hash VARCHAR(255) NOT NULL,         -- bcrypt
  nickname      VARCHAR(50)  NOT NULL,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- posts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
  id            BIGSERIAL PRIMARY KEY,
  author_id     BIGINT       NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title         VARCHAR(200) NOT NULL,
  body_markdown TEXT         NOT NULL,
  tags          TEXT[]       NOT NULL DEFAULT '{}',
  likes_count   BIGINT       NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_tags   ON posts USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);

-- ---------------------------------------------------------------------------
-- comments
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comments (
  id         BIGSERIAL PRIMARY KEY,
  post_id    BIGINT      NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  author_id  BIGINT      NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  content    TEXT        NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- post_likes (幂等点赞)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS post_likes (
  post_id    BIGINT      NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id    BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (post_id, user_id)
);

COMMIT;
