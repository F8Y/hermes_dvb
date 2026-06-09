"""Клиент MAX (userbot) — READ ONLY.

Сознательно НЕ реализованы методы отправки сообщений: класс физически
не умеет писать в MAX. Read-only гарантируется на уровне кода.

Message — нормализованное сообщение, которое ждёт коллектор.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    external_id: str
    text: str
    author_id: str | None = None
    posted_at: datetime | None = None
    url: str | None = None
    metrics: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class MaxUserbotClient:
    def __init__(self, session: str | None = None, proxy: str | None = None):
        self.session = session or os.environ.get("MAX_SESSION")
        self.proxy = proxy or os.environ.get("MAX_PROXY") or None
        self._connected = False

    async def connect(self) -> None:
        if not self.session:
            raise RuntimeError("MAX_SESSION не задан — нечем авторизовать userbot")
        # TODO(next step): поднять реальную сессию reverse-engineered клиента.
        self._connected = True

    async def fetch_messages(
        self, handle: str, since: datetime | None = None
    ) -> list[Message]:
        if not self._connected:
            await self.connect()
        raise NotImplementedError(
            "Сессионный клиент MAX ещё не подключён — это следующий шаг сборки. "
            "Каркас коллектора и схема БД уже готовы принимать Message."
        )

    async def close(self) -> None:
        self._connected = False
