"""Analyzer: берёт необработанные raw_items, классифицирует через Cloud.ru
(OpenAI-совместимый endpoint) и пишет результат в findings.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from openai import OpenAI

from common.db import connect, fetch_unanalyzed, save_finding
from prompt import SYSTEM, user_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analyzer")

BASE_URL = os.environ.get("CLOUDRU_BASE_URL")
API_KEY = os.environ.get("CLOUDRU_API_KEY")
MODEL = os.environ.get("CLOUDRU_MODEL")
BATCH = int(os.environ.get("ANALYZER_BATCH", "20"))
INTERVAL = int(os.environ.get("ANALYZER_INTERVAL", "60"))

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def _parse(content: str) -> dict | None:
    m = _JSON_RE.search(content or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def classify(text: str) -> dict | None:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_payload(text)},
        ],
        temperature=0,
        max_tokens=400,
    )
    data = _parse(resp.choices[0].message.content)
    if not data:
        return None
    # лёгкая нормализация
    if data.get("kind") not in ("fraud", "negative_review", "other"):
        data["kind"] = "other"
    return data


def run_batch() -> int:
    processed = 0
    with connect() as conn:
        items = fetch_unanalyzed(conn, BATCH)
        for it in items:
            try:
                finding = classify(it["text"])
            except Exception as e:  # noqa: BLE001
                log.warning("item %s: ошибка LLM %s", it["id"], e)
                continue
            if finding is None:
                log.warning("item %s: модель вернула невалидный JSON", it["id"])
                continue
            save_finding(conn, it["id"], finding, MODEL)
            processed += 1
        conn.commit()
    return processed


def main() -> None:
    if not (BASE_URL and API_KEY and MODEL):
        log.error("CLOUDRU_BASE_URL / CLOUDRU_API_KEY / CLOUDRU_MODEL не заданы")
        return
    log.info("analyzer запущен (model=%s, batch=%d)", MODEL, BATCH)
    while True:
        try:
            n = run_batch()
            if n:
                log.info("обработано %d items", n)
        except Exception as e:  # noqa: BLE001
            log.error("батч упал: %s", e)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
