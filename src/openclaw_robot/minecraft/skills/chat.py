"""对话技能：bot 在游戏聊天里发言。"""

from __future__ import annotations

from typing import Any


def say(bot: Any, message: str) -> str:
    """让 bot 在游戏聊天里发一条消息。"""
    bot.chat(message)
    return f"已发送：{message}"


def chat_tool(message: str) -> str:
    """在游戏聊天里发言。"""
    return f"已发送：{message}"
