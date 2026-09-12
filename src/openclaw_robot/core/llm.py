"""LLM provider 抽象：OpenAI 兼容接口，支持本地与云端部署。

切换后端只需改环境变量，无需改代码：
  云端 OpenAI:    LLM_API_BASE=https://api.openai.com/v1
  云端 DeepSeek:  LLM_API_BASE=https://api.deepseek.com
  本地 Ollama:    LLM_API_BASE=http://localhost:11434/v1
  本地 vLLM:      LLM_API_BASE=http://localhost:8000/v1
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# 常见后端预设（API base + 默认模型 + 占位 key）
PRESETS = {
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "deepseek": {
        "api_base": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "ollama": {
        "api_base": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "api_key": "ollama",  # Ollama 不校验 key，但 SDK 需要非空
    },
    "vllm": {
        "api_base": "http://localhost:8000/v1",
        "model": "qwen2.5-7b",
        "api_key": "EMPTY",
    },
    "siliconflow": {
        "api_base": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
    },
}


@dataclass
class LLM:
    """OpenAI 兼容的 LLM 客户端封装。

    通过环境变量配置：
      LLM_API_BASE, LLM_API_KEY, LLM_MODEL
    或用 LLM.create("ollama") 选预设。
    """

    api_base: str = ""
    api_key: str = ""
    model: str = ""

    def __post_init__(self) -> None:
        self.api_base = self.api_base or os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
        self.api_key = self.api_key or os.getenv("LLM_API_KEY", "")
        self.model = self.model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise RuntimeError(
                "LLM_API_KEY 未设置：云端需真实 key，本地 Ollama 填任意非空值（如 'ollama'）"
            )

    @classmethod
    def create(cls, preset: str, api_key: str = "", model: str = "") -> LLM:
        """用预设创建 LLM。

        preset: openai / deepseek / ollama / vllm / siliconflow
        api_key: 覆盖预设的 key（本地后端可省略）
        model: 覆盖预设的模型名
        """
        if preset not in PRESETS:
            raise ValueError(f"未知预设 {preset}，可选: {list(PRESETS)}")
        cfg = PRESETS[preset]
        return cls(
            api_base=cfg["api_base"],
            api_key=api_key or cfg.get("api_key", ""),
            model=model or cfg["model"],
        )

    @property
    def is_local(self) -> bool:
        """是否为本地部署（localhost / 127.0.0.1）。"""
        return "localhost" in self.api_base or "127.0.0.1" in self.api_base

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
