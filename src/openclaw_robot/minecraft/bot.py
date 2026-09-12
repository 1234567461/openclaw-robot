"""Minecraft bot 玩家主循环：连接服务器、监听聊天、LLM 决策、执行技能。

用 quarry（纯 Python MC 协议库）连接服务器。
收到玩家聊天 → 用 LLM 理解意图 → 调用工具（采集/建造/对话）→ 回复。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from ..core.llm import LLM
from ..core.tools import Tool, ToolRegistry
from .pathfinding import find_path
from .prompts import SYSTEM_PROMPT, WORLD_STATE_TEMPLATE
from .world import World

log = logging.getLogger(__name__)


@dataclass
class MinecraftBot:
    """一个 Minecraft 玩家 bot。

    配置通过环境变量：
      MC_HOST, MC_PORT, MC_USERNAME, MC_AUTH, MC_EMAIL, MC_PASSWORD
    """

    llm: LLM = field(default_factory=LLM)
    host: str = ""
    port: int = 25565
    username: str = "ClawBot"
    auth: str = "offline"
    email: str = ""
    password: str = ""

    # 运行时状态
    _factory: Any = field(default=None, repr=False)
    _protocol: Any = field(default=None, repr=False)
    _entity_id: int = 0
    _position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    _health: float = 20.0
    _inventory: dict[str, int] = field(default_factory=dict)
    _tools: ToolRegistry = field(default_factory=ToolRegistry)
    _chat_history: list[dict] = field(default_factory=list)
    _world: World = field(default_factory=World)

    def __post_init__(self) -> None:
        self.host = self.host or os.getenv("MC_HOST", "127.0.0.1")
        self.port = int(os.getenv("MC_PORT", "25565"))
        self.username = self.username or os.getenv("MC_USERNAME", "ClawBot")
        self.auth = os.getenv("MC_AUTH", "offline")
        self.email = os.getenv("MC_EMAIL", "")
        self.password = os.getenv("MC_PASSWORD", "")
        self._register_tools()

    # ---------- 工具注册 ----------

    def _register_tools(self) -> None:
        """把 bot 自身能力注册为 LLM 可调用的工具。"""
        self._tools.register(Tool(
            name="chat",
            description="在游戏聊天里发言。message: 要说的内容。",
            func=lambda message: self._do_chat(message),
        ))
        self._tools.register(Tool(
            name="gather",
            description="采集资源。resource: wood/stone/coal/iron/diamond，count: 数量。",
            func=lambda resource="wood", count=1: self._do_gather(resource, count),
        ))
        self._tools.register(Tool(
            name="build",
            description="在坐标(x,y,z)建造结构。structure: hut/tower/torch。",
            func=lambda structure, x, y, z: self._do_build(structure, x, y, z),
        ))
        self._tools.register(Tool(
            name="look_around",
            description="报告周围环境（前方方块）。",
            func=lambda: self._look_around(),
        ))
        self._tools.register(Tool(
            name="where",
            description="报告自己当前坐标和状态。",
            func=lambda: self._where(),
        ))

    # ---------- 工具实现 ----------

    def _do_chat(self, message: str) -> str:
        self.chat(message)
        return f"已发送：{message}"

    def _do_gather(self, resource: str, count: int) -> str:
        from .skills.gather import gather
        return gather(self, resource, count)

    def _do_build(self, structure: str, x: float, y: float, z: float) -> str:
        from .skills.build import build
        return build(self, structure, x, y, z)

    def _look_around(self) -> str:
        ahead = self._scan_ahead()
        return f"前方方块: {ahead}"

    def _where(self) -> str:
        return (
            f"坐标 ({self._position[0]:.0f}, {self._position[1]:.0f}, "
            f"{self._position[2]:.0f})，生命 {self._health}/20"
        )

    # ---------- quarry 交互层 ----------

    def chat(self, message: str) -> None:
        """发送聊天消息。"""
        if self._protocol is None:
            log.info("[MC 桩] chat: %s", message)
            return
        from quarry.net.protocol import ProtocolError  # type: ignore
        try:
            self._protocol.send_chat(message)
        except ProtocolError as e:
            log.error("发送聊天失败: %s", e)

    def find_nearest_block(self, block_names, radius: int = 16) -> Any:
        """扫描附近的目标方块（基于世界快照）。"""
        names = tuple(block_names) if not isinstance(block_names, tuple) else block_names
        center = (int(self._position[0]), int(self._position[1]), int(self._position[2]))
        return self._world.find_nearest_block(names, center, radius)

    def move_near(self, pos: tuple) -> bool:
        """用 A* 寻路移动到 pos 附近。

        桩模式（无 protocol）直接假定成功。
        连接模式下逐点发送位置包，模拟沿路径行走。
        """
        goal = (int(pos[0]), int(pos[1]), int(pos[2]))
        start = (int(self._position[0]), int(self._position[1]), int(self._position[2]))

        if self._protocol is None:
            self._position = (float(pos[0]), float(pos[1]), float(pos[2]))
            return True

        result = find_path(self._world, start, goal, max_steps=500)
        if not result:
            log.warning("无法寻路到 %s（路径不通）", goal)
            return False

        import time

        for step in result.path:
            self._position = (float(step[0]) + 0.5, float(step[1]), float(step[2]) + 0.5)
            self._protocol.send_position(*self._position)
            time.sleep(0.1)  # 避免发包过快被踢
        log.info("已走到 %s（%d 步）", goal, result.length)
        return True

    def dig_block(self, pos: tuple) -> bool:
        """挖掘 pos 处的方块。"""
        if self._protocol is None:
            return True
        # 实际：发送 player digging 包（start=0 destroy, start=1 stop）
        log.info("挖掘 %s", pos)
        return True

    def place_block(self, pos: tuple, block: str) -> bool:
        """在 pos 放置方块。"""
        if self._protocol is None:
            return True
        log.info("放置 %s @ %s", block, pos)
        return True

    def _scan_ahead(self) -> str:
        center = (int(self._position[0]), int(self._position[1]), int(self._position[2]))
        counts = self._world.blocks_around(center, radius=5)
        if not counts:
            return "（附近无已知方块，等待 chunk 加载）"
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
        return ", ".join(f"{n}:{c}" for n, c in top)

    # ---------- 聊天决策 ----------

    def on_player_chat(self, player: str, message: str) -> None:
        """收到玩家聊天 → LLM 决策 → 执行工具 → 回复。"""
        log.info("<%s> %s", player, message)
        # 忽略自己发的消息
        if player == self.username:
            return

        world_state = WORLD_STATE_TEMPLATE.format(
            x=self._position[0], y=self._position[1], z=self._position[2],
            health=self._health,
            inventory=dict(list(self._inventory.items())[:5]) or "空",
            nearby_players=player,
            ahead=self._scan_ahead(),
        )

        system = SYSTEM_PROMPT.format(bot_name=self.username)
        messages = [
            {"role": "system", "content": system + "\n" + world_state},
            {"role": "user", "content": f"[玩家 {player} 说]: {message}"},
        ]

        openai_tools = self._tools.to_openai()
        for _ in range(5):
            resp = self.llm.chat(messages, tools=openai_tools)
            msg = resp["choices"][0]["message"]
            messages.append(msg)
            if not msg.get("tool_calls"):
                if msg.get("content"):
                    self.chat(msg["content"])
                return
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                result = self._tools.call(fn["name"], fn.get("arguments", "{}"))
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    # ---------- 连接与主循环 ----------

    def connect(self) -> None:
        """连接到 MC 服务器。"""
        try:
            from quarry.net.client import ClientProtocol  # type: ignore
        except ImportError:
            log.warning("quarry 未安装，bot 运行在桩模式（不连接服务器）")
            return

        log.info("连接 MC 服务器 %s:%d（用户 %s）", self.host, self.port, self.username)

        class _Protocol(ClientProtocol):  # type: ignore[misc]
            bot = self

            def packet_player_chat(self, data) -> None:  # type: ignore[no-untyped-def]
                # 1.19+ chat 信号，实际用 chat_message
                pass

            def packet_chat_message(self, data) -> None:  # type: ignore[no-untyped-def]
                """收到聊天消息。data: {json: str, position: int, sender: str}"""
                import json
                try:
                    raw = data["json"]
                    msg = json.loads(raw) if isinstance(raw, str) else raw
                    text = _extract_text(msg)
                    if not text:
                        return
                    # 解析 "玩家> 消息" 格式
                    if ">" in text:
                        player, content = text.split(">", 1)
                        self.bot.on_player_chat(player.strip(), content.strip())
                    else:
                        self.bot.on_player_chat("server", text)
                except Exception as e:  # noqa: BLE001
                    log.debug("解析聊天失败: %s", e)

            def packet_position(self, data) -> None:  # type: ignore[no-untyped-def]
                self.bot._entity_id = data["entity_id"]
                self.bot._position = (data["x"], data["y"], data["z"])

            def packet_update_health(self, data) -> None:  # type: ignore[no-untyped-def]
                self.bot._health = data["health"]

            def packet_chunk_data(self, data) -> None:  # type: ignore[no-untyped-def]
                """收到区块数据：解析方块并写入世界快照。

                quarry 的 chunk data 包含 sections（16x16x16），
                每个 section 有 palette + block states。
                这里委托 World 处理，避免协议版本差异。
                """
                try:
                    _parse_chunk(self.bot._world, data)
                except Exception as e:  # noqa: BLE001
                    log.debug("解析 chunk 失败: %s", e)

            def packet_block_change(self, data) -> None:  # type: ignore[no-untyped-def]
                """单个方块变更（玩家挖掘/放置触发）。"""
                try:
                    loc = data["location"]
                    x, y, z = loc["x"], loc["y"], loc["z"]
                    bid = data["block_id"]
                    name = _block_id_to_name(bid)
                    self.bot._world.set_block(x, y, z, name)
                except Exception as e:  # noqa: BLE001
                    log.debug("解析 block_change 失败: %s", e)

            def packet_multi_block_change(self, data) -> None:  # type: ignore[no-untyped-def]
                """批量方块变更。"""
                try:
                    for chunk in data.get("chunks", []):
                        cx, cz = chunk["chunk_x"], chunk["chunk_z"]
                        for entry in chunk.get("records", []):
                            # 从 packed record 解析本地坐标 + block id
                            local_x = (entry >> 8) & 0x0F
                            local_z = (entry >> 4) & 0x0F
                            local_y = entry & 0x0F
                            bid = (entry >> 12) & 0xFFFF
                            name = _block_id_to_name(bid)
                            self.bot._world.set_block(
                                cx * 16 + local_x,
                                local_y,
                                cz * 16 + local_z,
                                name,
                            )
                except Exception as e:  # noqa: BLE001
                    log.debug("解析 multi_block_change 失败: %s", e)

        # quarry 的 ClientFactory 启动
        from quarry.net.client import ClientFactory  # type: ignore
        from twisted.internet import reactor  # type: ignore

        self._factory = ClientFactory(
            protocol=_Protocol,
            connect_host=self.host,
            connect_port=self.port,
            auth=self.auth,
            username=self.username,
            email=self.email,
            password=self.password,
        )
        self._factory.connect()
        reactor.run(installSignalHandlers=False)  # type: ignore[arg-type]

    def run_cli(self) -> None:
        """桩模式 / 调试模式：本地输入模拟玩家聊天。"""
        log.info("MC bot CLI 模式（输入玩家聊天，quit 退出）")
        while True:
            try:
                line = input("玩家> ")
            except (EOFError, KeyboardInterrupt):
                break
            if line.strip().lower() in {"quit", "exit"}:
                break
            if ">" in line:
                player, msg = line.split(">", 1)
                self.on_player_chat(player.strip(), msg.strip())
            else:
                self.on_player_chat("Tester", line)


def _extract_text(chat_component: Any) -> str:
    """从 MC chat JSON 组件提取纯文本。"""
    if isinstance(chat_component, str):
        return chat_component
    if isinstance(chat_component, dict):
        parts = [str(chat_component.get("text", ""))]
        for child in chat_component.get("extra", []):
            parts.append(_extract_text(child))
        return "".join(parts)
    if isinstance(chat_component, list):
        return "".join(_extract_text(c) for c in chat_component)
    return ""


def _block_id_to_name(block_id: int) -> str:
    """把方块数字 ID 转为名字（简化版）。

    完整映射需要协议版本的方块状态表（上千条），
    这里只处理常见 ID，未知的返回 "minecraft:unknown_<id>"。
    """
    _COMMON = {
        0: "minecraft:air",
        1: "minecraft:stone",
        2: "minecraft:grass_block",
        3: "minecraft:dirt",
        4: "minecraft:cobblestone",
        5: "minecraft:oak_planks",
        9: "minecraft:water",
        12: "minecraft:sand",
        15: "minecraft:iron_ore",
        16: "minecraft:coal_ore",
        17: "minecraft:oak_log",
        56: "minecraft:diamond_ore",
    }
    return _COMMON.get(block_id, f"minecraft:unknown_{block_id}")


def _parse_chunk(world: World, data: Any) -> None:
    """解析 chunk data 包，把方块写入 world。

    支持 Minecraft 1.18+ 的 chunk column 格式：
      sections: [{palette: [...], data: [64-bit longs]}, ...]
    palette 是方块状态表，data 是 packed bit array（每个值索引 palette）。

    解析出的每个方块按 (x, y, z) 写入 world；air 会被自动忽略。
    协议版本差异导致结构不匹配时静默跳过，后续 block_change 会增量更新。
    """
    if not isinstance(data, dict):
        return
    sections = data.get("sections")
    if not sections:
        return

    chunk_x = data.get("chunk_x", data.get("x", 0))
    chunk_z = data.get("chunk_z", data.get("z", 0))

    for sec_idx, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        palette = section.get("palette")
        block_states = section.get("data") or section.get("block_states") or section.get("states")
        if not palette or block_states is None:
            continue

        bits_per = max(4, _ceil_log2(len(palette)))
        states = _unpack_packed(block_states, bits_per, 16 * 16 * 16)
        base_y = sec_idx * 16

        for i, state_id in enumerate(states):
            if state_id >= len(palette):
                continue
            name = palette[state_id]
            if isinstance(name, dict):
                name = name.get("name")
            if not isinstance(name, str) or not name:
                continue
            local_x = i & 0x0F
            local_z = (i >> 4) & 0x0F
            local_y = (i >> 8) & 0x0F
            world.set_block(
                chunk_x * 16 + local_x,
                base_y + local_y,
                chunk_z * 16 + local_z,
                name,
            )


def _ceil_log2(n: int) -> int:
    """返回 ceil(log2(n))，n>=1。"""
    if n <= 1:
        return 0
    return (n - 1).bit_length()


def _unpack_packed(data: list[int], bits_per: int, count: int) -> list[int]:
    """把 64-bit long 数组解码为 count 个 bits_per 位的无符号值。

    Minecraft packed array 规则：每个 long 装 floor(64 / bits_per) 个值，
    从最低位开始，剩余高位忽略（值不跨 long 边界）。
    palette 大小通常是 2 的幂，bits_per = 4/8/16 等，都整除 64。
    """
    if bits_per <= 0:
        return []
    mask = (1 << bits_per) - 1
    values_per_long = 64 // bits_per
    result: list[int] = []
    for word in data:
        word &= 0xFFFFFFFFFFFFFFFF
        for i in range(values_per_long):
            if len(result) >= count:
                break
            result.append((word >> (i * bits_per)) & mask)
    # 数据不完整时补 0
    while len(result) < count:
        result.append(0)
    return result


def main() -> None:
    """命令行入口：启动 MC bot。"""
    import sys

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bot = MinecraftBot()

    if "--cli" in sys.argv:
        bot.run_cli()
    else:
        bot.connect()


if __name__ == "__main__":
    main()
