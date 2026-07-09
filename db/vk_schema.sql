-- ======================================================================
--  VK-таблицы — рабочее пространство агента (Beboopper пишет сюда сам).
--  Отдельно от raw_items (landing коллекторов): агент туда НЕ пишет.
--  Права: hermes_ro получает SELECT/INSERT/UPDATE на vk_*, но НЕ DELETE
--  (принцип «читать/дописывать, не разрушать» сохраняется).
--
--  Применить под владельцем:
--    docker compose exec -T postgres psql -U dvb -d dvbmon < db/vk_schema.sql
-- ======================================================================
-- ---- Расширяем platform/kind на существующих таблицах (идемпотентно) ----
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_platform_check;
ALTER TABLE sources
ADD CONSTRAINT sources_platform_check CHECK (platform IN ('tiktok', 'max', 'vk', 'ok'));
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_kind_check;
ALTER TABLE sources
ADD CONSTRAINT sources_kind_check CHECK (
        kind IN (
            'channel',
            'chat',
            'user',
            'hashtag',
            'keyword',
            'group'
        )
    );
ALTER TABLE raw_items DROP CONSTRAINT IF EXISTS raw_items_platform_check;
ALTER TABLE raw_items
ADD CONSTRAINT raw_items_platform_check CHECK (platform IN ('tiktok', 'max', 'vk', 'ok'));
-- ---- Посты со стен сообществ (wall.get) --------------------------------
CREATE TABLE IF NOT EXISTS vk_posts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT REFERENCES sources(id) ON DELETE
    SET NULL,
        community TEXT,
        -- короткое имя/домен сообщества
        owner_id BIGINT,
        -- VK owner_id (у сообщества отрицательный)
        post_id BIGINT,
        -- VK id поста
        url TEXT,
        posted_at TIMESTAMPTZ,
        text TEXT,
        metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        -- likes/comments/reposts/views
        raw JSONB NOT NULL DEFAULT '{}'::jsonb,
        collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (owner_id, post_id) -- дедуп поста
);
-- ---- Комментарии к постам (wall.getComments) ---------------------------
CREATE TABLE IF NOT EXISTS vk_comments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT REFERENCES sources(id) ON DELETE
    SET NULL,
        owner_id BIGINT,
        post_id BIGINT,
        comment_id BIGINT,
        author_hash TEXT,
        -- псевдонимизация автора (152-ФЗ)
        posted_at TIMESTAMPTZ,
        text TEXT,
        raw JSONB NOT NULL DEFAULT '{}'::jsonb,
        collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (owner_id, post_id, comment_id) -- дедуп комментария
);
-- полнотекст по русской морфологии
CREATE INDEX IF NOT EXISTS idx_vk_posts_fts ON vk_posts USING gin (to_tsvector('russian', text));
CREATE INDEX IF NOT EXISTS idx_vk_comments_fts ON vk_comments USING gin (to_tsvector('russian', text));
CREATE INDEX IF NOT EXISTS idx_vk_posts_time ON vk_posts (posted_at DESC);
-- ---- Права агенту: писать в свои vk-таблицы, без DELETE ------------------
GRANT SELECT,
    INSERT,
    UPDATE ON vk_posts,
    vk_comments TO hermes_ro;
-- DELETE/DROP не даём: «снять» запись = не удалять, а помечать в raw/metrics.