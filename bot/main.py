"""Точка входа для Telegram бота."""

import asyncio

from app.__main__ import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
