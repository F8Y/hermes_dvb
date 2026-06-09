"""
MAX Collector READ_ONLY
Так как в MAX очень агрессивные блокировки, коллектор парсит только верифицированные человеком источники
Источники, которые нашел Hermes попадают в candidates и ожидают верификации
"""

from __future__ import annotations

import asyncio
import logging
import os

from common.db import connect, insert_raw_item, list_active_sources
from client import MaxUserbotClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("max")

POLL_INTERVAL = int(os.environ.get("MAX_POLL_INTERVAL", "300"))


async def poll_once(client: MaxUserbotClient) -> None:
    with connect() as conn:
        sources = list_active_sources(conn, "max")
        if not sources:
            log.info("Нет активных источников MAX")
            return
        for src in sources:
            try:
                messages = await client.fetch_messages(src["handle"])
            except NotImplementedError as e:
                log.warning("источник %s: %s", src["handle"], e)
                return
            except Exception as e:
                log.warning("источник %s: ошибка чтения %s", src["handle"], e)
                continue
            stored = 0
            for m in messages:
                if not (m.text or "").strip():
                    continue
                new_id = insert_raw_item(
                    conn,
                    platform="max",
                    source_id=src["id"],
                    external_id=m.external_id,
                    url=m.url,
                    author_id=m.author_id,
                    posted_at=m.posted_at,
                    text=m.text,
                    metrics=m.metrics,
                    raw_json=m.raw,
                )
                if new_id:
                    stored += 1
            conn.commit()
            log.info("источник %s: новых %d", src["handle"], stored)


async def main() -> None:
    client = MaxUserbotClient()
    while True:
        try:
            await poll_once(client)
        except Exception as e:
            log.error("цикл упал: %s", e)
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "main":
    asyncio.run(main())
