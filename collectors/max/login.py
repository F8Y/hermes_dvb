# Одноразовый вход: телефон + SIM
# Запуск через прокси и .sh обертку

import asyncio
import asyncio
import os

from pymax import Client, ExtraConfig


async def main() -> None:
    phone = os.environ.get("MAX_PHONE") or input("Телефон (+7...): ").strip()

    client = Client(
        phone=phone,
        work_dir="/session",
        session_name="account.db",
        extra_config=ExtraConfig(reconnect=False, log_level="INFO"),
    )
    await client.start()

    me = getattr(client, "me", None)

    print(f"Вошли, ID: {getattr(getattr(me, 'contact', None))} id ?")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
