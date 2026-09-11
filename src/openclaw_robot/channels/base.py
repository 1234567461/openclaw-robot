"""渠道基类：定义与 Gateway 的对接接口。"""

from __future__ import annotations

import abc


class Channel(abc.ABC):
    """所有渠道（IM/物理机器人/MC）的抽象基类。

    子类实现：
      - on_message(user_id, text): 收到消息时调用，通常转发给 gateway.receive
      - send(user_id, text): 把回复发回渠道
      - run(): 启动渠道监听（阻塞）
    """

    name: str = "base"

    def __init__(self, gateway=None) -> None:
        self.gateway = gateway

    @abc.abstractmethod
    def send(self, user_id: str, text: str) -> None:
        """把文本回复发回渠道。"""

    @abc.abstractmethod
    def run(self) -> None:
        """启动渠道监听循环（阻塞）。"""

    def _dispatch(self, user_id: str, text: str) -> None:
        """收到消息后转发给 Gateway 处理，并把回复发回。"""
        if self.gateway is None:
            return
        reply = self.gateway.receive(self.name, user_id, text)
        self.send(user_id, reply)
