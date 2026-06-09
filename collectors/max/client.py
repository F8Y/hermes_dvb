"""
READ ONLY client для Max через сторонний userbot
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
            raise RuntimeError(
                "MAX_SESSION не задан, userbot не может быть инициализирован"
            )
            # TODO: Логика userbot'а

        self._connected = True

    async def fetch_messages(
        self, handle: str, since: datetime | None = None
    ) -> list[Message]:
        if not self._connected:
            await self.connect()
        raise NotImplementedError("Сессия Max еще не реализована")

    async def close(self) -> None:
        self._connected = False
