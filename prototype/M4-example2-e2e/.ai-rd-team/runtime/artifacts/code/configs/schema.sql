-- BlogAPI PostgreSQL schema
-- Owner: developer_1 (per architect spec-design.md §6)
-- Engine: PostgreSQL 15+

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nickname      VARCHAR(100) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS posts (
    id             BIGSERIAL PRIMARY KEY,
    author_id      BIGINT       NOT NULL REFERENCES users(id),
    title          VARCHAR(200) NOT NULL,
    body_markdown  TEXT         NOT NULL,
    tags           TEXT[]       NOT NULL DEFAULT '{}',
    likes_count    BIGINT       NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_tags   ON posts USING GIN (tags);

CREATE TABLE IF NOT EXISTS comments (
    id         BIGSERIAL PRIMARY KEY,
    post_id    BIGINT      NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id  BIGINT      NOT NULL REFERENCES users(id),
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at DESC);

CREATE TABLE IF NOT EXISTS post_likes (
    post_id    BIGINT      NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id    BIGINT      NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, user_id)
);
