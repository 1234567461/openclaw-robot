"""工具模块测试：验证 Tool 的 schema 推导与调用。"""

from openclaw_robot.core.tools import Tool, ToolRegistry


def add(a: int, b: int = 1) -> str:
    return str(a + b)


def test_tool_schema_inference():
    t = Tool(name="add", description="加法", func=add)
    schema = t.schema
    assert schema["type"] == "object"
    assert "a" in schema["properties"]
    assert "b" in schema["properties"]
    # a 无默认值 → required
    assert "a" in schema["required"]
    # b 有默认值 → 不 required
    assert "b" not in schema["required"]


def test_tool_run():
    t = Tool(name="add", description="加法", func=add)
    assert t.run(a=2, b=3) == "5"
    # 用默认值
    assert t.run(a=10) == "11"


def test_tool_run_returns_json_for_non_string():
    def info() -> dict:
        return {"ok": True}

    t = Tool(name="info", description="信息", func=info)
    result = t.run()
    assert '"ok"' in result and "true" in result.lower()


def test_registry_call_with_json_string():
    reg = ToolRegistry()
    reg.register(Tool(name="add", description="加法", func=add))
    # 字符串参数（LLM 返回的格式）
    assert reg.call("add", '{"a": 1, "b": 2}') == "3"
    # dict 参数
    assert reg.call("add", {"a": 4, "b": 5}) == "9"
    # 未知工具
    assert "未知工具" in reg.call("nope", "{}")


def test_tool_handles_exception():
    def boom(x: int) -> int:
        raise ValueError("炸了")

    t = Tool(name="boom", description="会爆炸", func=boom)
    result = t.run(x=1)
    assert "执行失败" in result
