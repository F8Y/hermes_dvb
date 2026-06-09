from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

_WS_RE = re.compile(r"\s+")


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL не задан в окружении")
    return dsn


@contextmanager
def connect():
    """Контекст-коннект с dict-строками и автокоммитом по выходу."""
    conn = psycopg.connect(_dsn(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip().lower())


def content_hash(platform: str, text: str) -> str:
    base = f"{platform}:{normalize_text(text)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def author_hash(author_id: str | None) -> str | None:
    if not author_id:
        return None
    salt = os.environ.get("AUTHOR_HASH_SALT", "")
    return hashlib.sha256(f"{salt}:{author_id}".encode("utf-8")).hexdigest()


def get_or_create_source(
    conn,
    platform: str,
    kind: str,
    handle: str,
    title: str | None = None,
    status: str = "candidate",
    discovered_by: str = "seed",
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources (platform, kind, handle, title, status, discovered_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (platform, kind, handle) DO UPDATE SET updated_at = now()
            RETURNING id
            """,
            (platform, kind, handle, title, status, discovered_by),
        )
        return cur.fetchone()["id"]


def insert_raw_item(
    conn,
    *,
    platform: str,
    text: str,
    source_id: int | None = None,
    external_id: str | None = None,
    url: str | None = None,
    author_id: str | None = None,
    posted_at: Any = None,
    lang: str | None = None,
    metrics: dict | None = None,
    raw_json: dict | None = None,
) -> int | None:
    chash = content_hash(platform, text)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_items
                (platform, source_id, external_id, url, author_hash,
                 posted_at, lang, text, metrics, raw_json, content_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (content_hash) DO NOTHING
            RETURNING id
            """,
            (
                platform,
                source_id,
                external_id,
                url,
                author_hash(author_id),
                posted_at,
                lang,
                text,
                json.dumps(metrics or {}, ensure_ascii=False),
                json.dumps(raw_json or {}, ensure_ascii=False),
                chash,
            ),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def fetch_unanalyzed(conn, limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, platform, text, url, posted_at
            FROM raw_items
            WHERE analyzed = FALSE
            ORDER BY collected_at
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (limit,),
        )
        return cur.fetchall()


def save_finding(conn, item_id: int, finding: dict, model: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO findings
                (item_id, kind, category, summary, severity,
                 sentiment, entities, confidence, model)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (item_id) DO NOTHING
            """,
            (
                item_id,
                finding.get("kind", "other"),
                finding.get("category"),
                finding.get("summary"),
                finding.get("severity"),
                finding.get("sentiment"),
                json.dumps(finding.get("entities", {}), ensure_ascii=False),
                finding.get("confidence"),
                model,
            ),
        )
        cur.execute("UPDATE raw_items SET analyzed = TRUE WHERE id = %s", (item_id,))


def list_active_sources(conn, platform: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, kind, handle, title FROM sources
            WHERE platform = %s AND status = 'active'
            """,
            (platform,),
        )
        return cur.fetchall()
