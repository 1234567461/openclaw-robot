"""IM 渠道适配器：把不同渠道的消息接入 Gateway。"""

from .base import Channel

__all__ = ["Channel"]


def __getattr__(name: str):
    """延迟导入可选渠道，避免未装依赖时 import 报错。"""
    if name == "WebChannel":
        from .web import WebChannel
        return WebChannel
    if name == "TelegramChannel":
        from .telegram import TelegramChannel
        return TelegramChannel
    if name == "FeishuChannel":
        from .feishu import FeishuChannel
        return FeishuChannel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
