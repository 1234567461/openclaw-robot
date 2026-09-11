"""Agent 主循环：感知→思考→行动，支持多轮工具调用。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .llm import LLM
from .memory import Memory
from .tools import ToolRegistry


@dataclass
class Agent:
    """一个 Agent = LLM + 记忆 + 工具集。

    典型用法：
        agent = Agent(llm=LLM(), memory=Memory(), tools=registry)
        reply = agent.handle("telegram", "user123", "帮我采点木头")
    """

    llm: LLM
    memory: Memory = field(default_factory=lambda: Memory())
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    system_prompt: str = "你是 openclaw-robot，一个能调用工具的 AI 机器人。"
    max_tool_rounds: int = 5

    def handle(self, channel: str, user_id: str, user_text: str) -> str:
        """处理一条用户消息，返回最终文本回复。"""
        ts = int(time.time())
        self.memory.append(channel, user_id, "user", user_text, ts)

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.memory.history(channel, user_id))

        openai_tools = self.tools.to_openai() or None

        for _ in range(self.max_tool_rounds):
            resp = self.llm.chat(messages, tools=openai_tools)
            msg = resp["choices"][0]["message"]
            messages.append(msg)

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                reply = msg.get("content", "")
                self.memory.append(channel, user_id, "assistant", reply, int(time.time()))
                return reply

            # 执行每个工具调用
            for tc in tool_calls:
                fn = tc["function"]
                result = self.tools.call(fn["name"], fn.get("arguments", "{}"))
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }
                messages.append(tool_msg)

        return "（工具调用轮次已达上限，停止处理）"
