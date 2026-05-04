-- BlogAPI schema (PostgreSQL 15)
-- Tables: users / posts / comments / post_likes

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL     PRIMARY KEY,
    email         VARCHAR(128)  NOT NULL UNIQUE,
    password_hash VARCHAR(128)  NOT NULL,
    nickname      VARCHAR(64)   NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS posts (
    id          BIGSERIAL     PRIMARY KEY,
    author_id   BIGINT        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(256)  NOT NULL,
    body        TEXT          NOT NULL DEFAULT '',
    tags        TEXT[]        NOT NULL DEFAULT '{}',
    like_count  BIGINT        NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_posts_author    ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_created   ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_tags_gin  ON posts USING GIN (tags);

CREATE TABLE IF NOT EXISTS comments (
    id          BIGSERIAL     PRIMARY KEY,
    post_id     BIGINT        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id   BIGINT        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body        TEXT          NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at);

-- 幂等点赞：联合主键保证每个用户对每篇文章只能点赞一次
CREATE TABLE IF NOT EXISTS post_likes (
    post_id     BIGINT        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id     BIGINT        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_post_likes_user ON post_likes(user_id);
