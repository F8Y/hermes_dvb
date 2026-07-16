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

## Все модели (просто для удобства: модель | цена входа | цена выхода):
- openai/text-embedding-3-large None 25.53 -1
- openai/text-embedding-3-small None 3.933 -1
- BAAI/bge-m3 None 0.61 0
- BAAI/bge-reranker-v2-m3 None 0.244 0
- hivetrace/HiveTracePro None 42.7 0
- Qwen/Qwen3-Embedding-0.6B None 0.854 0
- Qwen/Qwen3-Reranker-0.6B None 0.854 0
- Qwen/Qwen3-VL-Embedding-2B None 73.2 0
- Qwen/Qwen3-VL-Embedding-8B None 85.4 0
- Qwen/Qwen3-VL-Reranker-2B None 54.9 0
- Qwen/Qwen3-VL-Reranker-8B None 85.4 0
- openai/whisper-large-v3 None 0 0.0061
- ai-sage/GigaChat3-10B-A1.8B None 12.2 12.2
- openai/gpt-oss-20b None 5.888 27.4965
- Qwen/Qwen3-30B-A3B True 13.908 55.6076
- deepseek-ai/DeepSeek-OCR-2 None 54.9 61
- openai/gpt-oss-120b True 15.86 61
- openai/gpt-4.1-nano None 19.642 78.568
- openai/gpt-5-nano None 9.821 78.568
- openai/gpt-4o-mini None 29.463 117.852
- deepseek-ai/DeepSeek-V3 None 37.0758 148.291
- meituan-longcat/LongCat-Flash-Chat None 37.0758 148.291
- Qwen/Qwen3-32B True 37.0758 148.291
- deepseek-ai/DeepSeek-V3.1-Terminus True 74.1394 222.4182
- Qwen/Qwen3-Coder-Next None 122 244
- openai/gpt-5.4-nano None 39.284 245.525
- google/gemini-3.1-flash-lite-preview None 49.105 294.63
- deepseek-ai/DeepSeek-R1-0528 True 74.1394 296.5698
- deepseek-ai/DeepSeek-V4-Flash True 74.1394 296.5698
- openai/gpt-4.1-mini None 78.568 314.272
- Qwen/Qwen3.6-35B-A3B True 219.6 329.4
- openai/gpt-5-mini None 49.105 392.84
- MiniMaxAI/MiniMax-M2.5 True 353.8 475.8
- google/gemini-2.5-flash-image None 58.926 491.05
- google/gemini-2.5-flash None 58.926 491.05
- GigaChat/GigaChat-2-Max None 569.3374 569.3374
- google/gemini-3.1-flash-image-preview None 98.21 589.26
- google/gemini-3-flash-preview None 98.21 589.26
- moonshotai/Kimi-K2.6 True 175.68 725.9
- deepseek-ai/DeepSeek-V4-Pro True 183 732
- zai-org/GLM-4.7 True 549 793
- zai-org/GLM-5.1 True 198.86 829.6
- openai/gpt-5.4-mini None 147.315 883.89
- anthropic/claude-haiku-4.5 None 196.42 982.1
- Qwen/Qwen3.5-397B-A17B True 915 1085.8
- openai/gpt-4.1 None 392.84 1571.36
- google/gemini-2.5-pro None 245.525 1964.2
- openai/gpt-5.1-chat None 245.525 1964.2
- openai/gpt-5.1 None 245.525 1964.2
- openai/gpt-5-chat None 245.525 1964.2
- openai/gpt-5 None 245.525 1964.2
- google/gemini-3.1-pro-preview None 392.84 2357.04
- google/gemini-3-pro-image-preview None 392.84 2357.04
- openai/gpt-5.2-chat None 343.735 2749.88
- openai/gpt-5.2-codex None 343.735 2749.88
- openai/gpt-5.2 None 343.735 2749.88
- openai/gpt-5.3-chat None 343.735 2749.88
- openai/gpt-5.3-codex None 343.735 2749.88
- anthropic/claude-sonnet-4.5 None 589.26 2946.3
- anthropic/claude-sonnet-4.6 None 589.26 2946.3
- anthropic/claude-sonnet-4 None 589.26 2946.3
- openai/chatgpt-4o-latest None 982.1 2946.3
- openai/gpt-5.4 None 491.05 2946.3
- anthropic/claude-opus-4.5 None 982.1 4910.5
- anthropic/claude-opus-4.6 None 982.1 4910.5
- anthropic/claude-opus-4.1 None 2946.3 14731.5
- openai/gpt-5.4-pro None 5892.6 35355.6