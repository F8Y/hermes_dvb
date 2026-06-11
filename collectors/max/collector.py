"""MAX-коллектор (READ-ONLY) на PyMax.

Архитектура под событийную модель PyMax: client.start() блокируется и держит
соединение, поэтому вся работа — внутри on_start-хендлера. Одно постоянное
подключение, опрос в цикле (без повторных логинов = без re-auth-чехарды).

Читает историю только тех чатов, где аккаунт уже состоит (join делает человек
в приложении). Методов отправки нет by design. Трафик — через proxychains.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from pymax import Client, ExtraConfig

from common.db import (
    connect,
    insert_raw_item,
    list_active_sources,
    register_chat_source,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("max")

POLL = int(os.environ.get("MAX_POLL_INTERVAL", "300"))
BACKWARD = int(os.environ.get("MAX_BACKWARD", "50"))
# пауза между чтениями разных источников (анти-троттлинг + гигиена)
SOURCE_DELAY = float(os.environ.get("MAX_SOURCE_DELAY", "5"))

client = Client(
    phone=os.environ.get("MAX_PHONE"),
    work_dir="/session",
    session_name="account.db",
    extra_config=ExtraConfig(
        reconnect=True,
        reconnect_delay=5,
        log_level=os.environ.get("MAX_LOG_LEVEL", "INFO"),
    ),
)

_loop_started = False  # защита от дублирования цикла при reconnect


def _to_dt(ts):
    if not ts:
        return None
    try:
        ts = int(ts)
        return datetime.fromtimestamp(
            ts / 1000 if ts > 1_000_000_000_000 else ts, tz=timezone.utc
        )
    except (ValueError, TypeError, OSError):
        return None


def _resolve(chats, handle: str):
    """chat_id среди чатов, где аккаунт состоит, по handle (link/title)."""
    needle = handle.lstrip("@").strip().lower()
    for c in chats or []:
        for attr in ("link", "title"):
            v = getattr(c, attr, None)
            if v and needle in str(v).lower():
                return getattr(c, "id", None)
    return None


def _chat_id_for(handle: str, chats):
    """Если handle — числовой chat_id, берём его напрямую; иначе фуззи-резолв."""
    h = str(handle)
    if h.lstrip("-").isdigit():
        return int(h)
    return _resolve(chats, h)


def _register_joined(conn, chats) -> None:
    """Авто-регистрация всех joined чатов/каналов как КАНДИДАТОВ (не DIALOG)."""
    for c in chats or []:
        ctype = str(getattr(c, "type", "") or "").upper()
        if ctype not in ("CHAT", "CHANNEL"):
            continue
        cid = getattr(c, "id", None)
        title = getattr(c, "title", None)
        if cid is None or not title:
            continue
        register_chat_source(
            conn,
            platform="max",
            kind="channel" if ctype == "CHANNEL" else "chat",
            handle=str(cid),
            title=title,
            link=getattr(c, "link", None),
        )


async def poll_once():
    try:
        chats = await client.fetch_chats()
    except Exception as e:  # noqa: BLE001
        log.warning("fetch_chats: %s", e)
        return

    with connect() as conn:
        # авто-регистрация всех joined чатов как кандидатов (статус не трогаем)
        _register_joined(conn, chats)
        conn.commit()

        sources = list_active_sources(conn, "max")
        if not sources:
            log.info(
                "нет активных источников MAX — кандидаты записаны, "
                "подтвердите нужные (status='active')"
            )
            return
        for src in sources:
            cid = _chat_id_for(src["handle"], chats)
            if cid is None:
                log.warning(
                    "источник %s: аккаунт не состоит — вступите в приложении MAX",
                    src["handle"],
                )
                continue
            try:
                hist = await client.fetch_history(chat_id=cid, backward=BACKWARD)
            except Exception as e:  # noqa: BLE001
                log.warning("источник %s: история: %s", src["handle"], e)
                continue

            stored = 0
            for m in hist or []:
                text = getattr(m, "text", None) or ""
                if not text.strip():
                    continue
                author = getattr(m, "sender", None)  # sender — это int-id юзера
                try:
                    raw = m.model_dump(mode="json") if hasattr(m, "model_dump") else {}
                except Exception:  # noqa: BLE001
                    raw = {}
                new_id = insert_raw_item(
                    conn,
                    platform="max",
                    source_id=src["id"],
                    external_id=str(getattr(m, "id", "") or ""),
                    author_id=str(author) if author else None,
                    posted_at=_to_dt(getattr(m, "time", None)),
                    text=text,
                    raw_json=raw,
                )
                if new_id:
                    stored += 1
            conn.commit()
            log.info("источник %s: новых %d", src["handle"], stored)
            await asyncio.sleep(SOURCE_DELAY)  # не читать источники залпом


@client.on_start()
async def on_start(_client):
    global _loop_started
    if _loop_started:
        return  # при reconnect не плодим второй цикл
    _loop_started = True
    log.info(
        "MAX userbot подключён — старт опроса (poll=%ds, backward=%d)", POLL, BACKWARD
    )
    while True:
        try:
            await poll_once()
        except Exception as e:  # noqa: BLE001
            log.error("цикл упал: %s", e)
        await asyncio.sleep(POLL)


if __name__ == "__main__":
    try:
        asyncio.run(client.start())
    except Exception as e:  # noqa: BLE001
        # PyMax падает на нераспарсиваемом кадре (напр. error-код -14).
        # Пауза перед выходом, чтобы рестарт контейнера не спамил логинами.
        log.error("сессия завершилась: %s — пауза 60с перед рестартом", e)
        time.sleep(60)
