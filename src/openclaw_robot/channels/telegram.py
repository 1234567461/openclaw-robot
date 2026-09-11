"""Telegram 渠道适配器（依赖可选安装：pip install openclaw-robot[telegram]）。"""

from __future__ import annotations

import logging
import os

from .base import Channel

log = logging.getLogger(__name__)


class TelegramChannel(Channel):
    """基于 python-telegram-bot 的渠道实现。"""

    name = "telegram"

    def __init__(self, gateway=None) -> None:
        super().__init__(gateway)
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not self.token:
            log.warning("TELEGRAM_BOT_TOKEN 未设置，Telegram 渠道不可用")
        self._app = None

    def send(self, user_id: str, text: str) -> None:
        if self._app is None:
            log.warning("Telegram 未启动，无法发送")
            return
        import asyncio

        async def _send() -> None:
            await self._app.bot.send_message(chat_id=user_id, text=text)

        try:
            asyncio.get_event_loop().run_until_complete(_send())
        except RuntimeError:
            asyncio.new_event_loop().run_until_complete(_send())

    def run(self) -> None:
        if not self.token:
            return
        from telegram import Update
        from telegram.ext import Application, CommandHandler, MessageHandler, filters

        self._app = Application.builder().token(self.token).build()

        async def on_msg(update: Update, _ctx) -> None:
            if update.message and update.message.text:
                user_id = str(update.message.chat_id)
                self._dispatch(user_id, update.message.text)

        self._app.add_handler(CommandHandler("start", lambda u, c: None))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))
        log.info("Telegram 渠道已启动")
        self._app.run_polling()
