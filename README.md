# Hermes-dbv

Анализ публичных источников в TikTok и MAX: сбор → классификация
(фрод / негативные отзывы) → хранение в PostgreSQL. Только чтение и анализ,
система ничего не публикует.

## Архитектура (v1)

```
TikTok ─┐
        ├─ collectors ──> PostgreSQL (raw_items) ──> analyzer ──> findings
MAX  ───┘   (read-only)                              (Cloud.ru LLM)
```

Сервисы (`docker-compose.yml`):

| Сервис            | Что делает                                              |
|-------------------|---------------------------------------------------------|
| `postgres`        | хранилище: `raw_items` (сырьё) + `findings` (разметка)  |
| `tiktok-collector`| скрап TikTok по ключам про Сбер (TikTokApi + Playwright)|
| `max-collector`   | userbot MAX, **отдельный аккаунт**, read-only           |
| `analyzer`        | классификация фрод/негатив через Cloud.ru LLM           |

Полноценный агент **Hermes** (Telegram-вывод, автопоиск источников) —
следующий слой поверх этих таблиц.

## Запуск на сервере

> Образы собираются **на сервере** (amd64). Не собирайте на Apple Silicon.

```bash
git clone <repo-url> hermes-dvb
cd hermes-dvb
cp .env.example .env       # заполнить ключи (см. ниже)
nano .env
docker compose up -d --build
docker compose logs -f analyzer
```

## Заполнение .env

- `POSTGRES_*`, `DATABASE_URL` — пароль БД (придумать свой, одинаковый в обоих).
- `AUTHOR_HASH_SALT` — случайная строка (псевдонимизация авторов, 152-ФЗ).
- `CLOUDRU_BASE_URL` / `CLOUDRU_API_KEY` / `CLOUDRU_MODEL` — доступ к Cloud.ru
  Evolution Models (OpenAI-совместимый endpoint).
- `TIKTOK_MS_TOKEN` — значение cookie `msToken` с tiktok.com (DevTools →
  Application → Cookies). Периодически протухает.
- `TIKTOK_PROXY` / `MAX_PROXY` — residential-прокси (для TikTok практически
  обязателен, иначе детект бота).
- `MAX_SESSION` — сессия отдельного аккаунта MAX (подключим на след. шаге).

## Данные

- `raw_items` — всё собранное, хранится один раз; переразметка возможна без
  повторного скрапинга. Дедуп по `content_hash`. Автор — только `author_hash`.
- `findings` — `kind` ∈ `fraud` / `negative_review` / `other`, `category` —
  свободный текст (таксономию замораживаем позже по реальным данным).
- Представления: `v_fraud`, `v_reviews`.

Примеры запросов:

```sql
-- свежий фрод
SELECT category, summary, severity, url, posted_at
FROM v_fraud ORDER BY collected_at DESC LIMIT 50;

-- топ категорий жалоб за неделю
SELECT category, count(*) FROM v_reviews
WHERE collected_at > now() - interval '7 days'
GROUP BY category ORDER BY 2 DESC;
```

## Источники (sources)

Коллектор MAX читает только источники со `status='active'` — то есть
**подтверждённые человеком**. Кандидаты (`status='candidate'`), в том числе
предложенные агентом, не читаются до ручного перевода в `active`. Это снижает
риск бана userbot-аккаунта и отсекает мусорные источники.

```sql
-- одобрить канал к чтению
UPDATE sources SET status='active', approved_by='you'
WHERE platform='max' AND handle='<канал>';
```

## Юридическое / риски

- MAX userbot нарушает ToS MAX и рискует баном аккаунта — используется **burner**,
  не основной аккаунт.
- Собираются персональные данные третьих лиц → 152-ФЗ: авторы псевдонимизированы,
  минимизация по умолчанию.
- Система только фиксирует и анализирует уже опубликованное; она не исполняет
  и не распространяет описанные схемы.

## Статус

- [x] Каркас: БД, compose, коллекторы, analyzer
- [ ] Реальный сессионный клиент MAX (`collectors/max/client.py`)
- [ ] Hermes: Telegram-вывод + автопоиск источников с верификацией
- [ ] Семантический дедуп схем (pgvector)