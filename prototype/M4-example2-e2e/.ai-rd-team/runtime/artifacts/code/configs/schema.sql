-- BlogAPI schema (PostgreSQL 15+)
-- Author: architect
-- 说明：
--   * 所有时间戳用 TIMESTAMPTZ
--   * tags 用 TEXT[]，配合 GIN 索引支持按 tag 过滤
--   * post_likes 联合主键保证点赞幂等
--   * posts.likes_count 为冗余字段，由业务事务维护

BEGIN;

-- ========== users ==========
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(128) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    nickname      VARCHAR(64)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_users_email ON users (email);

-- ========== posts ==========
CREATE TABLE IF NOT EXISTS posts (
    id             BIGSERIAL PRIMARY KEY,
    author_id      BIGINT       NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title          VARCHAR(200) NOT NULL,
    body_markdown  TEXT         NOT NULL,
    tags           TEXT[]       NOT NULL DEFAULT '{}',
    likes_count    BIGINT       NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_posts_author_id   ON posts (author_id);
CREATE INDEX IF NOT EXISTS idx_posts_created_at  ON posts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_tags_gin    ON posts USING GIN (tags);

-- ========== comments ==========
CREATE TABLE IF NOT EXISTS comments (
    id         BIGSERIAL PRIMARY KEY,
    post_id    BIGINT      NOT NULL REFERENCES posts (id) ON DELETE CASCADE,
    author_id  BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_post_created
    ON comments (post_id, created_at DESC);

-- ========== post_likes ==========
CREATE TABLE IF NOT EXISTS post_likes (
    post_id    BIGINT      NOT NULL REFERENCES posts (id) ON DELETE CASCADE,
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_post_likes_user ON post_likes (user_id);

COMMIT;
