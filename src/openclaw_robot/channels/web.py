"""Web 聊天渠道：浏览器里和 Agent 对话（WebSocket 实时通信）。

依赖（可选安装）：pip install openclaw-robot[web]
启动：openclaw-web
打开：http://localhost:8080
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .base import Channel

log = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


class WebChannel(Channel):
    """基于 FastAPI + WebSocket 的网页聊天渠道。

    一个浏览器标签页 = 一个用户会话（user_id 用 websocket id）。
    支持：
    - 实时双向消息（WebSocket）
    - 历史记录展示
    - 接入 Gateway / Agent，复用记忆与工具
    """

    name = "web"

    def __init__(self, gateway=None, host: str = "", port: int = 0) -> None:
        super().__init__(gateway)
        self.host = host or os.getenv("WEB_HOST", "0.0.0.0")
        self.port = port or int(os.getenv("WEB_PORT", "8080"))
        self._app: Any = None
        self._clients: dict[str, Any] = {}

    def _build_app(self) -> Any:
        """构建 FastAPI app（延迟导入 fastapi）。"""
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse
        from fastapi.staticfiles import StaticFiles

        app = FastAPI(title="openclaw-robot web chat")
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def index() -> str:
            """返回聊天前端页面。"""
            index_html = _STATIC_DIR / "index.html"
            return index_html.read_text(encoding="utf-8")

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            ws_id = str(id(websocket))
            self._clients[ws_id] = websocket
            log.info("Web 客户端连接 %s", ws_id)
            try:
                while True:
                    text = await websocket.receive_text()
                    # 转发到 Gateway / Agent 处理
                    if self.gateway:
                        import asyncio
                        reply = await asyncio.get_event_loop().run_in_executor(
                            None, self.gateway.receive, self.name, ws_id, text
                        )
                        await websocket.send_text(reply)
                    else:
                        await websocket.send_text("（Gateway 未配置）")
            except WebSocketDisconnect:
                log.info("Web 客户端断开 %s", ws_id)
            finally:
                self._clients.pop(ws_id, None)

        @app.get("/health")
        async def health() -> dict:
            return {"status": "ok", "clients": len(self._clients)}

        return app

    def send(self, user_id: str, text: str) -> None:
        """把回复发回指定客户端。WebSocket 模式下回复在 ws handler 里直接发，这里给 CLI 调试用。"""
        ws = self._clients.get(user_id)
        if ws:
            import asyncio

            asyncio.get_event_loop().run_until_complete(ws.send_text(text))

    def run(self) -> None:
        """启动 FastAPI + uvicorn 服务器。"""
        if self._app is None:
            self._app = self._build_app()
        import uvicorn

        log.info("Web 聊天渠道启动: http://%s:%d", self.host, self.port)
        uvicorn.run(self._app, host=self.host, port=self.port, log_level="info")


def main() -> None:
    """命令行入口：启动 Web 聊天。"""
    from ..core.agent import Agent
    from ..core.gateway import Gateway
    from ..core.llm import LLM
    from ..core.memory import Memory
    from ..core.tools import ToolRegistry

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    gw = Gateway(
        agent=Agent(
            llm=LLM(),
            memory=Memory(),
            tools=ToolRegistry(),
            system_prompt="你是 openclaw-robot，通过网页和用户对话。简洁友好。",
        )
    )
    web = WebChannel(gateway=gw)
    gw.register("web", web)
    web.run()


if __name__ == "__main__":
    main()
