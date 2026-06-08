"""
Analyzer: берет необработанные raw_items классифицирует через Hermes и пишет результат в findings
Вывод аналитики Hermes делает через шлюз Telegram
"""

import logging
from __future__ import annotations
import json
import re
import os
import logging
import json

from openai import OpenAI
from common.db import connect, fetch_unanalyzed, save_finding
from prompt import SYSTEM, user_payload

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("analyzer")

BASE_URL = os.environ.get("CLOUDRU_BASE_URL")
API_KEY = os.environ.get("CLOUDRU_API_KEY")
MODEL = os.environ.get("CLOUDRU_MODEL")
BATCH = int(os.environ.get("ANALYZER_BATCH", "20"))
INTERVAL = int(os.environ.get("ANALYZER_INTERVAL", "60"))

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def parse(content: str) -> dict | None:
    m = _JSON_RE.search(content or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
