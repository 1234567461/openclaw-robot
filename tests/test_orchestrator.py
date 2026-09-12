"""Orchestrator 多 Agent 编排测试。"""


from openclaw_robot.core.llm import LLM
from openclaw_robot.core.orchestrator import Orchestrator


def test_orchestrator_no_specialist():
    """无 specialist 时返回提示。"""
    orch = Orchestrator(llm=_FakeLLM())
    result = orch.delegate("做点什么", "cli", "u1")
    assert "没有可用" in result


def test_orchestrator_single_specialist_direct():
    """只有一个 specialist 时直接路由（不调 LLM）。"""
    orch = Orchestrator(llm=_FakeLLM())
    agent = _FakeAgent()
    orch.add_specialist("doer", "干活的", agent)
    result = orch.delegate("任务", "cli", "u1")
    assert "[doer]" in result


def test_orchestrator_routes_to_matching_specialist():
    """多个 specialist 时用 LLM 路由。"""
    orch = Orchestrator(llm=_FakeLLM(reply="miner"))
    orch.add_specialist("miner", "挖矿", _FakeAgent(reply="挖到铁"))
    orch.add_specialist("builder", "建造", _FakeAgent(reply="建好了"))
    result = orch.delegate("挖矿", "cli", "u1")
    assert "[miner]" in result
    assert "挖到铁" in result


def test_llm_presets_exist():
    """预设覆盖常见后端。"""
    from openclaw_robot.core.llm import PRESETS

    assert "openai" in PRESETS
    assert "ollama" in PRESETS
    assert "deepseek" in PRESETS
    assert "vllm" in PRESETS


def test_llm_is_local_property():
    """is_local 判定本地后端。"""
    llm = LLM(api_base="http://localhost:11434/v1", api_key="x", model="m")
    assert llm.is_local
    llm2 = LLM(api_base="https://api.openai.com/v1", api_key="x", model="m")
    assert not llm2.is_local


# ---------- 测试替身 ----------


class _FakeLLM:
    """假 LLM：chat_text 返回固定回复，不真正调 API。"""

    def __init__(self, reply: str = "ok") -> None:
        self._reply = reply

    def chat_text(self, prompt: str, system: str = "") -> str:
        return self._reply

    def chat(self, messages, tools=None, temperature=0.7):
        return {"choices": [{"message": {"content": self._reply, "tool_calls": None}}]}


class _FakeAgent:
    """假 Agent：handle 返回固定回复。"""

    def __init__(self, reply: str = "done") -> None:
        self._reply = reply
        self.memory = _FakeMemory()

    def handle(self, channel: str, user_id: str, text: str) -> str:
        return self._reply


class _FakeMemory:
    """假 Memory：append 空操作。"""

    def append(self, *args, **kwargs) -> None:
        pass
