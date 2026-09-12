"""多 Agent 编排：Orchestrator 把任务路由到最合适的专门 Agent。

类似 OpenClaw 的多 Agent 架构：每个 Agent 有自己的工具集与系统提示，
Orchestrator 用 LLM 判断任务类型并分派，最后汇总结果。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from .agent import Agent
from .llm import LLM
from .memory import Memory
from .tools import ToolRegistry

log = logging.getLogger(__name__)


@dataclass
class SpecialistAgent:
    """一个专门 Agent：名字 + 描述（供路由判断）+ 实际 Agent。"""

    name: str
    description: str  # 给 Orchestrator 看的能力描述
    agent: Agent


@dataclass
class Orchestrator:
    """多 Agent 编排器。

    用法：
        orch = Orchestrator(llm=LLM())
        orch.add_specialist("miner", "负责采集和挖掘", miner_agent)
        orch.add_specialist("builder", "负责建造", builder_agent)
        result = orch.delegate("帮我挖 10 个石头", "cli", "u1")
    """

    llm: LLM
    specialists: dict[str, SpecialistAgent] = field(default_factory=dict)
    system_prompt: str = (
        "你是任务编排器。根据用户任务选择最合适的专门 Agent 执行。"
        "只能选一个 specialist，把任务交给它。"
    )
    max_delegates: int = 3

    def add_specialist(self, name: str, description: str, agent: Agent) -> SpecialistAgent:
        """注册一个专门 Agent。"""
        sa = SpecialistAgent(name=name, description=description, agent=agent)
        self.specialists[name] = sa
        return sa

    def _route(self, task: str) -> str | None:
        """用 LLM 决定任务分给哪个 specialist。"""
        if not self.specialists:
            return None
        if len(self.specialists) == 1:
            return next(iter(self.specialists))

        roster = "\n".join(
            f"- {name}: {sa.description}" for name, sa in self.specialists.items()
        )
        resp = self.llm.chat_text(
            f"可选 specialist：\n{roster}\n\n任务：{task}\n\n只回复 specialist 名字。",
            system=self.system_prompt,
        )
        chosen = resp.strip().lower()
        # 容错：LLM 可能输出多余内容，提取匹配的名字
        for name in self.specialists:
            if name in chosen:
                return name
        log.warning("Orchestrator 路由结果 %r 未匹配任何 specialist", chosen)
        return None

    def delegate(self, task: str, channel: str = "cli", user_id: str = "local") -> str:
        """分派任务到专门 Agent，返回其回复。"""
        ts = int(time.time())
        target_name = self._route(task)
        if target_name is None:
            return "没有可用的 specialist 处理此任务"

        sa = self.specialists[target_name]
        log.info("任务路由：%s → %s", task[:40], target_name)
        # 记录原始任务到该 specialist 的记忆
        sa.agent.memory.append(channel, user_id, "user", task, ts)
        reply = sa.agent.handle(channel, user_id, task)
        return f"[{target_name}] {reply}"


def build_default_orchestrator(llm: LLM | None = None) -> Orchestrator:
    """构建默认的 MC bot 编排器：对话/采集/建造三个 specialist。

    便于快速启动：每个 specialist 共享 LLM 但有独立记忆和工具子集。
    """
    _llm = llm or LLM()

    orch = Orchestrator(llm=_llm)

    # 对话 specialist：只能聊天
    chat_agent = Agent(
        llm=_llm,
        memory=Memory(),
        tools=ToolRegistry(),
        system_prompt="你是 MC 服务器里的聊天 bot，只能对话，不能采集或建造。",
    )
    orch.add_specialist("chat", "负责与玩家对话、回答问题", chat_agent)

    return orch
