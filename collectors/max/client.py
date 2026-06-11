"""MAX userbot-клиент (READ-ONLY) поверх PyMax (maxapi-python).

Принципы:
  * Читаем историю только тех чатов/каналов, где аккаунт УЖЕ состоит.
    В каналы вступает человек вручную в приложении MAX (join — самое
    небезопасное действие, userbot его не делает). Коллектор только читает.
  * Сетевой трафик идёт через RU mobile SOCKS5 (proxychains на уровне
    контейнера, см. entrypoint.sh) — PyMax про прокси не знает.

Поля PyMax-сообщений (time/sender/...) могут приходить неполными — берутся
защитно через getattr и проверяем на throwaway-аккаунте перед боевым.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pymax import Client, ExtraConfig

log = logging.getLogger("max.client")


@dataclass
class Message:
    external_id: str
    text: str
    author_id: str | None = None
    posted_at: datetime | None = None
    url: str | None = None
    metrics: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def _to_dt(ts) -> datetime | None:
    if not ts:
        return None
    try:
        ts = int(ts)
        # MAX отдаёт миллисекунды — приводим к секундам
        return datetime.fromtimestamp(
            ts / 1000 if ts > 1_000_000_000_000 else ts, tz=timezone.utc
        )
    except (ValueError, TypeError, OSError):
        return None


class MaxUserbotClient:
    """Read-only. send/answer/react здесь намеренно не реализованы."""

    def __init__(
        self,
        phone: str | None = None,
        work_dir: str = "/session",
        session_name: str = "account.db",
        backward: int = 50,
    ):
        self.phone = phone or os.environ.get("MAX_PHONE")
        self.work_dir = work_dir
        self.session_name = session_name
        self.backward = backward
        self._client: Client | None = None

    async def connect(self) -> None:
        if self._client:
            return
        if not self.phone:
            raise RuntimeError("MAX_PHONE не задан — нечем авторизоваться")
        self._client = Client(
            phone=self.phone,
            work_dir=self.work_dir,
            session_name=self.session_name,
            extra_config=ExtraConfig(
                reconnect=True,
                reconnect_delay=5,
                log_level=os.environ.get("MAX_LOG_LEVEL", "INFO"),
            ),
        )
        # start() использует сохранённую сессию из work_dir; SMS только если её нет
        await self._client.start()
        me = getattr(self._client, "me", None)
        log.info(
            "MAX подключён (me=%s)", getattr(getattr(me, "contact", None), "id", "?")
        )

    async def _resolve_chat_id(self, handle: str) -> int | None:
        """Найти chat_id среди чатов, где аккаунт УЖЕ состоит, по handle/title."""
        try:
            chats = await self._client.fetch_chats()
        except Exception as e:  # noqa: BLE001
            log.warning("fetch_chats упал: %s", e)
            chats = getattr(self._client, "chats", None)
        needle = handle.lstrip("@").strip().lower()
        for chat in chats or []:
            for attr in ("link", "username", "title", "name"):
                val = getattr(chat, attr, None)
                if val and needle in str(val).lower():
                    return getattr(chat, "id", None)
        return None

    async def fetch_messages(
        self, handle: str, since: datetime | None = None
    ) -> list[Message]:
        if not self._client:
            await self.connect()

        chat_id = await self._resolve_chat_id(handle)
        if chat_id is None:
            log.warning(
                "источник %s: аккаунт в этом чате не состоит — "
                "вступите вручную в приложении MAX",
                handle,
            )
            return []

        history = await self._client.fetch_history(
            chat_id=chat_id, backward=self.backward
        )
        out: list[Message] = []
        for m in history or []:
            posted = _to_dt(getattr(m, "time", None) or getattr(m, "timestamp", None))
            if since and posted and posted <= since:
                continue
            text = getattr(m, "text", None) or ""
            # sender в MAX — это сразу int-id пользователя, не объект
            author = getattr(m, "sender", None)
            try:
                raw = m.model_dump(mode="json") if hasattr(m, "model_dump") else {}
            except Exception:  # noqa: BLE001
                raw = {}
            out.append(
                Message(
                    external_id=str(getattr(m, "id", "") or ""),
                    text=text,
                    author_id=str(author) if author else None,
                    posted_at=posted,
                    metrics={},
                    raw=raw,
                )
            )
        return out

    async def close(self) -> None:
        if self._client:
            try:
                await self._client.close()
            except Exception:  # noqa: BLE001
                pass
        self._client = None
