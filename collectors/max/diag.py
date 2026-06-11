"""Диагностика MAX: вывести чаты аккаунта и сырой payload одного сообщения.

Нужно, чтобы подогнать `_resolve_chat_id` (по каким полям матчить канал) и
маппинг полей в client.py (как называются time/sender в Message).

Запуск (по уже сохранённой сессии, без SMS):
    docker compose run --rm -it max-collector python diag.py
"""

import asyncio
import json
import os
import signal

from pymax import Client, ExtraConfig

client = Client(
    phone=os.environ.get("MAX_PHONE"),
    work_dir="/session",
    session_name="account.db",
    extra_config=ExtraConfig(reconnect=False, log_level="INFO"),
)


@client.on_start()
async def on_start(client: Client) -> None:
    chats = await client.fetch_chats()
    print(f"\n=== ЧАТЫ ({len(chats or [])}) ===")
    for c in chats or []:
        print(
            "id=",
            getattr(c, "id", None),
            "| title=",
            repr(getattr(c, "title", None)),
            "| link=",
            getattr(c, "link", None),
            "| username=",
            getattr(c, "username", None),
            "| type=",
            getattr(c, "type", None),
        )

    if chats:
        cid = getattr(chats[0], "id", None)
        print(f"\n=== ИСТОРИЯ chat_id={cid} (до 2 сообщений, raw) ===")
        try:
            hist = await client.fetch_history(chat_id=cid, backward=2)
            for m in hist or []:
                raw = m.model_dump(mode="json") if hasattr(m, "model_dump") else {}
                print(json.dumps(raw, ensure_ascii=False, default=str)[:1500])
        except Exception as e:  # noqa: BLE001
            print("fetch_history error:", e)

    os.kill(os.getpid(), signal.SIGINT)  # завершить разовый прогон


if __name__ == "__main__":
    try:
        asyncio.run(client.start())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
