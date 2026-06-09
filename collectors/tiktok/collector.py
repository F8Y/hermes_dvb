"""TikTok-коллектор: ищет публичные видео по ключам и пишет в raw_items.

READ-ONLY: только чтение публичных данных. Ничего не постит.
Требует ms_token (из cookies tiktok.com) и residential-прокси для стабильности.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from TikTokApi import TikTokApi

from common.db import connect, get_or_create_source, insert_raw_item

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tiktok")

MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN") or None
PROXY = os.environ.get("TIKTOK_PROXY") or None
KEYWORDS = [
    k.strip() for k in os.environ.get("TIKTOK_KEYWORDS", "").split(",") if k.strip()
]
MAX_PER_RUN = int(os.environ.get("TIKTOK_MAX_PER_RUN", "50"))
INTERVAL = int(os.environ.get("TIKTOK_INTERVAL", "3600"))


def _proxies():
    return [PROXY] if PROXY else None


def _posted_at(video_dict: dict):
    ts = video_dict.get("createTime")
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _store_video(conn, source_id: int, video) -> bool:
    d = video.as_dict
    desc = d.get("desc") or ""
    if not desc.strip():
        return False
    author = d.get("author") or {}
    stats = d.get("stats") or {}
    vid = d.get("id")
    new_id = insert_raw_item(
        conn,
        platform="tiktok",
        source_id=source_id,
        external_id=vid,
        url=f"https://www.tiktok.com/@{author.get('uniqueId', '')}/video/{vid}"
        if vid
        else None,
        author_id=author.get("id"),
        posted_at=_posted_at(d),
        lang=d.get("textExtra") and None or d.get("language"),
        text=desc,
        metrics={
            "likes": stats.get("diggCount"),
            "comments": stats.get("commentCount"),
            "plays": stats.get("playCount"),
            "shares": stats.get("shareCount"),
        },
        raw_json=d,
    )
    return new_id is not None


async def run_once(api: TikTokApi) -> None:
    with connect() as conn:
        for kw in KEYWORDS:
            tag = kw.replace(" ", "").lstrip("#")
            source_id = get_or_create_source(
                conn,
                "tiktok",
                "hashtag",
                tag,
                title=kw,
                status="active",
                discovered_by="seed",
            )
            stored = 0
            try:
                async for video in api.hashtag(name=tag).videos(count=MAX_PER_RUN):
                    if _store_video(conn, source_id, video):
                        stored += 1
                conn.commit()
                log.info("tag #%s: новых %d", tag, stored)
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                log.warning("tag #%s: ошибка %s", tag, e)


async def main() -> None:
    if not KEYWORDS:
        log.error("TIKTOK_KEYWORDS пуст — нечего искать")
        return
    while True:
        try:
            async with TikTokApi() as api:
                await api.create_sessions(
                    ms_tokens=[MS_TOKEN] if MS_TOKEN else None,
                    num_sessions=1,
                    sleep_after=3,
                    proxies=_proxies(),
                    browser=os.getenv("TIKTOK_BROWSER", "chromium"),
                    headless=True,
                )
                await run_once(api)
        except Exception as e:  # noqa: BLE001
            log.error("цикл упал: %s", e)
        log.info("сон %d сек", INTERVAL)
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
