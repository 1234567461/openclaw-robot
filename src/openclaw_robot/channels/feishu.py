"""飞书渠道适配器（依赖可选安装：pip install openclaw-robot[feishu]）。

用 lark-oapi 接收事件回调。需在飞书开放平台创建自建应用，
开启「机器人」能力，订阅 im.message.receive_v1 事件。
"""

from __future__ import annotations

import logging
import os

from .base import Channel

log = logging.getLogger(__name__)


class FeishuChannel(Channel):
    """飞书 IM 机器人渠道。"""

    name = "feishu"

    def __init__(self, gateway=None) -> None:
        super().__init__(gateway)
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        if not (self.app_id and self.app_secret):
            log.warning("FEISHU_APP_ID/SECRET 未设置，飞书渠道不可用")

    def send(self, user_id: str, text: str) -> None:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        client = lark.Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()
        req = (
            CreateMessageRequest()
            .request_body(
                CreateMessageRequestBody()
                .receive_id(user_id)
                .msg_type("text")
                .content('{"text":"' + text.replace('"', '\\"') + '"}')
            )
        )
        client.im.v1.message.create(req)

    def run(self) -> None:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

        if not (self.app_id and self.app_secret):
            return

        client = lark.Client.builder().app_id(self.app_id).app_secret(self.app_secret).build()
        # client 已建立长连接能力，事件经 WsClient 下发
        _ = client  # noqa: F841 保留 client 引用避免被回收

        def handle(ctx: lark.EventDispatcherHandler, data: P2ImMessageReceiveV1) -> None:
            msg = data.event.message
            if msg.message_type == "text":
                import json

                content = json.loads(msg.content)
                self._dispatch(msg.chat_id, content.get("text", ""))

        event_handler = (
            lark.EventDispatcher.builder("", "")
            .register_p2_im_message_receive_v1(handle)
            .build()
        )
        cli = (
            lark.WsClient.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .handler(event_handler)
            .build()
        )
        log.info("飞书渠道已启动（WebSocket）")
        cli.start()
