-- ======================================================================
--  Доточка прав роли hermes_ro: разрешаем агенту вести таблицу sources.
--  Граница безопасности — права роли: читать всё, писать ТОЛЬКО в sources.
--  НИКАКИХ delete/drop/прочих таблиц — даже если MCP их предложит, Postgres
--  откажет. Применить ОДИН раз:
--    docker compose exec -T postgres psql -U dvb -d dvbmon < db/hermes_sources_grant.sql
-- ======================================================================
-- агент добавляет кандидатов и меняет их статус (флаги)
GRANT INSERT,
    UPDATE ON sources TO hermes_ro;
-- DELETE сознательно НЕ даём: «снять» источник = перевести status в 'rejected',
-- а не удалять строку. Дропа/чужих таблиц у роли нет и не будет.
-- проверка прав роли (для глаз):
-- SELECT grantee, table_name, privilege_type
--   FROM information_schema.role_table_grants WHERE grantee = 'hermes_ro';