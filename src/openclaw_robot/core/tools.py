"""工具注册与调度：Agent 通过 function-calling 调用注册的工具。"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    """一个可被 LLM 调用的工具。

    name: 工具名（LLM 调用时用）
    description: 给 LLM 看的描述
    func: 实际执行的 Python 函数
    schema: OpenAI function-calling 的 JSON Schema（自动从 func 签名推导）
    """

    name: str
    description: str
    func: Callable[..., Any]
    schema: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.schema:
            self.schema = _infer_schema(self.func)

    def run(self, **kwargs: Any) -> str:
        """执行工具，返回字符串结果给 LLM。"""
        try:
            result = self.func(**kwargs)
        except Exception as e:  # noqa: BLE001
            return f"工具 {self.name} 执行失败: {e}"
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)

    def to_openai(self) -> dict:
        """转成 OpenAI tools 参数格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> Tool:
        self.tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def to_openai(self) -> list[dict]:
        return [t.to_openai() for t in self.tools.values()]

    def call(self, name: str, arguments: dict | str) -> str:
        tool = self.get(name)
        if tool is None:
            return f"未知工具: {name}"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                arguments = {"_raw": arguments}
        return tool.run(**arguments)


def _infer_schema(func: Callable[..., Any]) -> dict:
    """从函数签名推导 JSON Schema（简化版）。"""
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        annot = param.annotation
        t = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}.get(
            getattr(annot, "__name__", ""), "string"
        )
        properties[pname] = {"type": t}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {"type": "object", "properties": properties, "required": required}
