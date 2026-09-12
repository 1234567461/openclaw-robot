"""MC bot RCON 命令构造测试。

验证 bot 把高层操作（chat/dig/place/move）正确翻译成 RCON 命令。
桩模式下 _rcon_cmd 返回空，但命令字符串会被记录，可验证格式。
"""

from openclaw_robot.core.llm import LLM
from openclaw_robot.minecraft.bot import MinecraftBot


def make_bot(monkeypatch):
    """桩模式 bot：不连服务器，_rcon_cmd 记录命令到列表。"""
    monkeypatch.delenv("MC_RCON_PASSWORD", raising=False)
    bot = MinecraftBot(llm=LLM.create("ollama"), username="ClawBot")
    calls: list[str] = []
    bot._rcon = object()       # 让 _connected 判断走真分支
    bot._connected = True
    bot._rcon_cmd = lambda cmd: (calls.append(cmd), "")[1]  # 记录并返回空
    return bot, calls


def test_chat_uses_tellraw(monkeypatch):
    """聊天用 /tellraw @a（1.19+ /say 已弃用）。"""
    bot, calls = make_bot(monkeypatch)
    bot.chat("你好")
    assert len(calls) == 1
    assert calls[0].startswith("tellraw @a")
    assert "ClawBot" in calls[0]
    assert "你好" in calls[0]


def test_chat_escapes_quotes(monkeypatch):
    """消息中的双引号被转义，避免破坏 JSON。"""
    bot, calls = make_bot(monkeypatch)
    bot.chat('他说"嗨"')
    assert '\\"' in calls[0]


def test_dig_block_command(monkeypatch):
    """挖掘用 /setblock air destroy。"""
    bot, calls = make_bot(monkeypatch)
    bot.dig_block((10, 64, -5))
    assert calls[0] == "setblock 10 64 -5 air destroy"


def test_place_block_command(monkeypatch):
    """放置用 /setblock。"""
    bot, calls = make_bot(monkeypatch)
    bot.place_block((10, 64, -5), "minecraft:stone")
    assert calls[0] == "setblock 10 64 -5 minecraft:stone"


def test_move_near_uses_tp(monkeypatch):
    """移动用 /tp 直接传送（RCON 模式无需寻路）。"""
    bot, calls = make_bot(monkeypatch)
    bot.move_near((100, 70, 200))
    assert calls[0] == "tp ClawBot 100 70 200"
    assert bot._position == (100.0, 70.0, 200.0)


def test_move_near_stub_no_connection(monkeypatch):
    """桩模式（无 RCON）直接更新坐标，不发命令。"""
    monkeypatch.delenv("MC_RCON_PASSWORD", raising=False)
    bot = MinecraftBot(llm=LLM.create("ollama"), username="ClawBot")
    # _connected=False, _rcon=None
    ok = bot.move_near((50, 60, 70))
    assert ok
    assert bot._position == (50.0, 60.0, 70.0)


def test_refresh_state_parses_position(monkeypatch):
    """_refresh_state 能从 RCON 响应解析坐标。"""
    bot, calls = make_bot(monkeypatch)

    def fake_cmd(cmd: str) -> str:
        calls.append(cmd)
        if "Pos" in cmd:
            return "ClawBot has the following entity data: [123.5d, 64.0d, -45.2d]"
        if "Health" in cmd:
            return "ClawBot has the following entity data: 18.0f"
        return ""

    bot._rcon_cmd = fake_cmd
    calls.clear()
    bot._refresh_state()
    assert bot._position == (123.5, 64.0, -45.2)
    assert bot._health == 18.0


def test_dig_returns_true_on_empty_response(monkeypatch):
    """桩/空响应视为成功（RCON 有时不返回内容）。"""
    bot, _ = make_bot(monkeypatch)
    bot._rcon_cmd = lambda cmd: ""
    assert bot.dig_block((1, 2, 3)) is True


def test_place_returns_true_on_changed(monkeypatch):
    """响应含 'Changed' 视为成功。"""
    bot, _ = make_bot(monkeypatch)
    bot._rcon_cmd = lambda cmd: "Changed the block"
    assert bot.place_block((1, 2, 3), "minecraft:stone") is True
