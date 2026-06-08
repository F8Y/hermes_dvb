-- ======================================================================
--  hermes-dvb — схема БД
--  Слои:
--    sources    — откуда читаем (каналы/чаты/хэштеги), статус заходов
--    raw_items  — landing: ВСЁ собранное (хранится один раз, можно
--                 переразмечать без повторного скрапинга)
--    findings   — результат классификации (фрод / негатив), пишет analyzer
--  Псевдонимизация: автор хранится только как author_hash (152-ФЗ).
-- ======================================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- pgvector подключим позже для семантического дедупа:
-- CREATE EXTENSION IF NOT EXISTS vector;
-- ----------------------------------------------------------------------
--  sources
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform TEXT NOT NULL CHECK (platform IN ('tiktok', 'max')),
    kind TEXT NOT NULL CHECK (
        kind IN ('channel', 'chat', 'user', 'hashtag', 'keyword')
    ),
    handle TEXT NOT NULL,
    -- @канал / #хэштег / поисковый запрос
    title TEXT,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (
        status IN (
            'candidate',
            'approved',
            'active',
            'banned',
            'rejected'
        )
    ),
    discovered_by TEXT,
    -- 'human' | 'hermes' | 'seed'
    approved_by TEXT,
    -- кто подтвердил заход (для userbot)
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, kind, handle)
);
-- ----------------------------------------------------------------------
--  raw_items — landing-таблица
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform TEXT NOT NULL CHECK (platform IN ('tiktok', 'max')),
    source_id BIGINT REFERENCES sources(id) ON DELETE
    SET NULL,
        external_id TEXT,
        -- id поста/сообщения на платформе
        url TEXT,
        author_hash TEXT,
        -- соль+id автора; личность не восстановить
        posted_at TIMESTAMPTZ,
        -- когда опубликовано (если отдаёт платформа)
        collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        lang TEXT,
        text TEXT NOT NULL,
        metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        -- лайки/просмотры/комменты
        raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        -- полный сырой payload
        content_hash TEXT NOT NULL,
        -- sha256 нормализованного текста — дедуп
        analyzed BOOLEAN NOT NULL DEFAULT FALSE,
        -- забрал ли analyzer
        UNIQUE (content_hash)
);
CREATE INDEX IF NOT EXISTS idx_raw_unanalyzed ON raw_items (collected_at)
WHERE analyzed = FALSE;
CREATE INDEX IF NOT EXISTS idx_raw_platform ON raw_items (platform, posted_at DESC);
-- Полнотекст по русской морфологии:
CREATE INDEX IF NOT EXISTS idx_raw_fts ON raw_items USING gin (to_tsvector('russian', text));
-- ----------------------------------------------------------------------
--  findings — классификация
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS findings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id BIGINT NOT NULL REFERENCES raw_items(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('fraud', 'negative_review', 'other')),
    -- category — СВОБОДНЫЙ текст, таксономию замораживаем позже по реальным данным
    category TEXT,
    summary TEXT,
    -- нормализованная суть (для дедупа смыслов)
    severity SMALLINT CHECK (
        severity BETWEEN 1 AND 5
    ),
    sentiment REAL,
    -- -1..1 (для отзывов)
    entities JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- продукты: SberPay, Спасибо...
    confidence REAL,
    model TEXT,
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (item_id) -- один разбор на item (v1)
);
CREATE INDEX IF NOT EXISTS idx_find_kind ON findings (kind, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_find_category ON findings (category);
-- ----------------------------------------------------------------------
--  Удобные представления для вывода (фрод / отзывы)
-- ----------------------------------------------------------------------
CREATE OR REPLACE VIEW v_fraud AS
SELECT f.id,
    f.category,
    f.summary,
    f.severity,
    f.entities,
    f.confidence,
    r.platform,
    r.url,
    r.posted_at,
    r.collected_at,
    r.text
FROM findings f
    JOIN raw_items r ON r.id = f.item_id
WHERE f.kind = 'fraud';
CREATE OR REPLACE VIEW v_reviews AS
SELECT f.id,
    f.category,
    f.summary,
    f.severity,
    f.sentiment,
    f.confidence,
    r.platform,
    r.url,
    r.posted_at,
    r.collected_at,
    r.text
FROM findings f
    JOIN raw_items r ON r.id = f.item_id
WHERE f.kind = 'negative_review';