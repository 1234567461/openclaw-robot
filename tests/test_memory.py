"""Memory 模块测试：会话历史隔离与读写。"""

import tempfile

from openclaw_robot.core.memory import Memory


def test_memory_round_trip():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        mem = Memory(f.name)
        mem.append("cli", "u1", "user", "你好", 1)
        mem.append("cli", "u1", "assistant", "你好啊", 2)
        hist = mem.history("cli", "u1")
        assert len(hist) == 2
        assert hist[0]["role"] == "user"
        assert hist[1]["role"] == "assistant"
        mem.close()


def test_memory_scope_isolation():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        mem = Memory(f.name)
        mem.append("cli", "u1", "user", "A", 1)
        mem.append("telegram", "u2", "user", "B", 1)
        assert len(mem.history("cli", "u1")) == 1
        assert len(mem.history("telegram", "u2")) == 1
        assert mem.history("cli", "u1")[0]["content"] == "A"
        mem.close()


def test_memory_limit():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        mem = Memory(f.name)
        for i in range(30):
            mem.append("cli", "u1", "user", str(i), i)
        hist = mem.history("cli", "u1", limit=10)
        assert len(hist) == 10
        # 最新 10 条，倒序读后翻转 → 最后一条应是 29
        assert hist[-1]["content"] == "29"
        mem.close()


def test_memory_clear():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        mem = Memory(f.name)
        mem.append("cli", "u1", "user", "hi", 1)
        mem.clear("cli", "u1")
        assert mem.history("cli", "u1") == []
        mem.close()
