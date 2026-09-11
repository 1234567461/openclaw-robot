"""LLM provider 抽象：OpenAI 兼容接口，可接 OpenAI/DeepSeek/本地 Ollama 等。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LLM:
    """OpenAI 兼容的 LLM 客户端封装。

    通过环境变量配置：
      LLM_API_BASE, LLM_API_KEY, LLM_MODEL
    """

    api_base: str = ""
    api_key: str = ""
    model: str = ""

    def __post_init__(self) -> None:
        self.api_base = self.api_base or os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
        self.api_key = self.api_key or os.getenv("LLM_API_KEY", "")
        self.model = self.model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY 未设置：请在 .env 或环境变量中提供")

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> dict:
        """调用 chat completions。返回完整 response dict。

        messages: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
        tools: OpenAI function-calling 格式的工具定义
        """
        from openai import OpenAI

        client = OpenAI(base_url=self.api_base, api_key=self.api_key)
        kwargs: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
        resp = client.chat.completions.create(**kwargs)
        return resp.model_dump()

    def chat_text(self, prompt: str, system: str = "你是一个有用的助手。") -> str:
        """简单文本对话，返回 assistant 文本。"""
        r = self.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        return r["choices"][0]["message"]["content"]
