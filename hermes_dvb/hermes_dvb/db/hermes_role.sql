-- ======================================================================
--  Read-only роль для Hermes (least-privilege).
--  Hermes только ЧИТАЕТ raw_items/findings/sources/views. Писать не может.
--  Кандидатов в источники он предлагает в Telegram — добавляете вы вручную.
--
--  Применить ОДИН раз (пароль впишите свой вместо CHANGE_ME_RO,
--  реальный пароль в git НЕ коммитим):
--    docker compose exec -T postgres psql -U dvb -d dvbmon < db/hermes_role.sql
-- ======================================================================
DO $$ BEGIN IF NOT EXISTS (
    SELECT
    FROM pg_roles
    WHERE rolname = 'hermes_ro'
) THEN CREATE ROLE hermes_ro LOGIN PASSWORD 'CHANGE_ME';
-- Чтобы не хардкодить пароль роли - задается через nano
END IF;
END $$;
GRANT CONNECT ON DATABASE dvbmon TO hermes_ro;
GRANT USAGE ON SCHEMA public TO hermes_ro;
-- SELECT на все текущие таблицы и представления (включая v_fraud/v_reviews)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO hermes_ro;
-- и на будущие таблицы — тоже только чтение
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO hermes_ro;
-- Гарантия: никаких прав на запись/DDL у роли нет.