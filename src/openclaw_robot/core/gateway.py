"""Gateway 控制面：把来自不同渠道的消息路由到 Agent。

类似 OpenClaw 的 Gateway（Control Plane）设计：
  Channel (IM/物理机器人/MC) → Gateway → Agent → 工具
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .agent import Agent

log = logging.getLogger(__name__)


@dataclass
class Gateway:
    """消息网关：注册 channel handler，统一路由到 Agent。"""

    agent: Agent
    handlers: dict[str, object] = field(default_factory=dict)

    def register(self, channel: str, handler: object) -> None:
        """注册一个渠道处理器。

        handler 需实现 on_message(text, user_id) -> None 并通过 gateway.send 回复。
        """
        self.handlers[channel] = handler

    def receive(self, channel: str, user_id: str, text: str) -> str:
        """接收消息 → Agent 处理 → 返回回复文本。"""
        log.info("[%s] %s: %s", channel, user_id, text[:80])
        reply = self.agent.handle(channel, user_id, text)
        log.info("[%s] reply: %s", channel, reply[:80])
        return reply

    def send(self, channel: str, user_id: str, text: str) -> None:
        """把 Agent 回复发回渠道。"""
        handler = self.handlers.get(channel)
        if handler and hasattr(handler, "send"):
            handler.send(user_id, text)  # type: ignore[attr-defined]
        else:
            log.warning("渠道 %s 无 send 实现，回复已丢弃: %s", channel, text[:80])


def main() -> None:
    """命令行入口：本地 REPL 调试 Agent。"""
    import os

    from .llm import LLM
    from .memory import Memory
    from .tools import ToolRegistry

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    gw = Gateway(agent=Agent(llm=LLM(), memory=Memory(), tools=ToolRegistry()))
    print("openclaw-gateway 本地 REPL（输入 quit 退出）")
    while True:
        try:
            text = input("你> ")
        except (EOFError, KeyboardInterrupt):
            break
        if text.strip().lower() in {"quit", "exit"}:
            break
        print("bot>", gw.receive("cli", "local", text))


if __name__ == "__main__":
    main()
