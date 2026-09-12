"""Minecraft bot 玩家主循环：通过 RCON 连接服务器、监听聊天、LLM 决策、执行技能。

RCON 是 MC 1.9+ 内置协议，版本无关（1.20/1.21/1.26 均可用）。
需在 server.properties 开启：
  enable-rcon=true
  rcon.password=<password>
  rcon.port=25575

收到玩家聊天（通过 RCON 查询日志或外部桥接）→ LLM 理解意图 → 调用工具 → 回复。
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from ..core.llm import LLM
from ..core.tools import Tool, ToolRegistry
from .prompts import SYSTEM_PROMPT, WORLD_STATE_TEMPLATE
from .world import World

log = logging.getLogger(__name__)


@dataclass
class MinecraftBot:
    """一个 Minecraft 玩家 bot，通过 RCON 与服务器交互。

    配置通过环境变量：
      MC_HOST, MC_RCON_PORT, MC_RCON_PASSWORD, MC_USERNAME
    RCON 需在 server.properties 开启（见模块 docstring）。
    """

    llm: LLM = field(default_factory=LLM)
    host: str = ""
    rcon_port: int = 25575
    rcon_password: str = ""
    username: str = "ClawBot"

    # 运行时状态
    _rcon: Any = field(default=None, repr=False)
    _mf_proc: Any = field(default=None, repr=False)  # mineflayer 子进程
    _connected: bool = False
    _position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    _health: float = 20.0
    _inventory: dict[str, int] = field(default_factory=dict)
    _tools: ToolRegistry = field(default_factory=ToolRegistry)
    _world: World = field(default_factory=World)

    def __post_init__(self) -> None:
        self.host = self.host or os.getenv("MC_HOST", "127.0.0.1")
        self.rcon_port = int(os.getenv("MC_RCON_PORT", "25575"))
        self.rcon_password = os.getenv("MC_RCON_PASSWORD", "")
        self.username = os.getenv("MC_USERNAME", "ClawBot")
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
        # 用 /execute 查询脚下和前方方块
        blocks = []
        for dx, dz in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            x = int(self._position[0]) + dx
            z = int(self._position[2]) + dz
            block = self._rcon_cmd(f"data get block {x} {int(self._position[1])} {z}")
            if block and "is not a block entity" not in block.lower():
                blocks.append(f"({x},{z}):{block[:30]}")
        return "前方方块: " + (", ".join(blocks) if blocks else "（无法读取）")

    def _where(self) -> str:
        return (
            f"坐标 ({self._position[0]:.0f}, {self._position[1]:.0f}, "
            f"{self._position[2]:.0f})，生命 {self._health}/20"
        )

    # ---------- RCON 交互层 ----------

    def _rcon_cmd(self, command: str) -> str:
        """执行一条 RCON 命令，返回服务器响应。桩模式返回空。"""
        if not self._connected or self._rcon is None:
            log.info("[MC 桩] rcon: %s", command)
            return ""
        try:
            return self._rcon.command(command)
        except Exception as e:  # noqa: BLE001
            log.error("RCON 命令失败 %s: %s", command, e)
            return ""

    def chat(self, message: str) -> None:
        """在游戏聊天发言（/say）。"""
        # /say 在 1.19+ 已弃用，新版用 /tellraw @a
        safe = message.replace('"', '\\"')
        self._rcon_cmd(f'tellraw @a {{"text":"<{self.username}> {safe}"}}')

    def find_nearest_block(self, block_names, radius: int = 16) -> Any:
        """扫描附近目标方块。

        RCON 无法直接查询方块，这里用 /execute 空间扫描（性能有限）。
        完整方案需 /loot 或外部桥接，这里给出简化版。
        """
        names = tuple(block_names) if not isinstance(block_names, tuple) else block_names
        center = (int(self._position[0]), int(self._position[1]), int(self._position[2]))
        return self._world.find_nearest_block(names, center, radius)

    def move_near(self, pos: tuple) -> bool:
        """移动到 pos 附近（用 /tp 直接传送，RCON 模式下无需寻路）。"""
        if not self._connected:
            self._position = (float(pos[0]), float(pos[1]), float(pos[2]))
            return True
        x, y, z = pos[0], pos[1], pos[2]
        resp = self._rcon_cmd(f"tp {self.username} {x} {y} {z}")
        if "Teleported" in resp or not resp:
            self._position = (float(x), float(y), float(z))
            log.info("已传送到 (%.0f, %.0f, %.0f)", x, y, z)
            return True
        log.warning("传送失败: %s", resp)
        return False

    def dig_block(self, pos: tuple) -> bool:
        """挖掘 pos 处的方块（/setblock air）。"""
        x, y, z = pos[0], pos[1], pos[2]
        resp = self._rcon_cmd(f"setblock {x} {y} {z} air destroy")
        return "Changed" in resp or not resp

    def place_block(self, pos: tuple, block: str) -> bool:
        """在 pos 放置方块（/setblock）。"""
        x, y, z = pos[0], pos[1], pos[2]
        resp = self._rcon_cmd(f"setblock {x} {y} {z} {block}")
        return "Changed" in resp or not resp

    def _scan_ahead(self) -> str:
        return self._look_around()

    # ---------- 聊天决策 ----------

    def on_player_chat(self, player: str, message: str) -> None:
        """收到玩家聊天 → LLM 决策 → 执行工具 → 回复。"""
        log.info("<%s> %s", player, message)
        if player == self.username:
            return

        # 查询当前状态（通过 RCON）
        self._refresh_state()

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

    def _refresh_state(self) -> None:
        """通过 RCON 查询 bot 的当前坐标、生命、背包。"""
        if not self._connected:
            return
        # 查询坐标（1.13+ 的 /data get entity）
        pos_resp = self._rcon_cmd(f"data get entity {self.username} Pos")
        if pos_resp:
            match = re.search(r"\[([-\d.]+)d?,\s*([-\d.]+)d?,\s*([-\d.]+)d?\]", pos_resp)
            if match:
                self._position = (
                    float(match.group(1)),
                    float(match.group(2)),
                    float(match.group(3)),
                )
        # 查询生命
        health_resp = self._rcon_cmd(
            f"data get entity {self.username} Health"
        )
        if health_resp:
            match = re.search(r"([\d.]+)", health_resp)
            if match:
                self._health = float(match.group(1))

    # ---------- 连接与主循环 ----------

    def _try_mineflayer(self) -> bool:
        """用 mineflayer（Node.js 桥接）作为真实玩家连接。

        mineflayer 支持 MC 1.8~26.1，bot 是真实玩家实体（出现在玩家列表）。
        26.2 等上游合并后再支持；现在用 26.1。

        收到玩家聊天 → 写到 stdout（JSON）→ Python 读 stdout 回调 on_player_chat。
        需要 Node.js + npm install mineflayer。
        """
        try:
            import subprocess

            result = subprocess.run(  # noqa: S603,S602
                ["node", "-e", "require('mineflayer')"],
                capture_output=True, timeout=3,
            )
            if result.returncode != 0:
                log.info("mineflayer 未安装，回退 RCON")
                return False
        except FileNotFoundError:
            log.info("Node.js 未安装，回退 RCON")
            return False
        except subprocess.TimeoutExpired:
            log.info("Node.js 检测超时，回退 RCON")
            return False

        log.info("mineflayer 玩家模式连接 %s:25565（bot %s）", self.host, self.username)
        # JS 脚本：连服务器，监听聊天，每行输出 JSON {user,msg}，收到指令调 LLM
        script = (
            "const mf=require('mineflayer');"
            f"const b=mf.createBot({{host:'{self.host}',port:25565,"
            f"username:'{self.username}',version:'26.1',auth:'offline'}});"
            "b.on('spawn',()=>{b.chat('ClawBot 已上线');});"
            "b.on('chat',(u,m)=>{"
            "if(u!==b.username)console.log(JSON.stringify({user:u,msg:m}));"
            "});"
            "b.on('kicked',r=>console.error('kicked',r));"
            "b.on('error',e=>console.error('error',e));"
            "b.on('end',()=>console.error('disconnected'));"
        )
        try:
            import subprocess as sp

            self._mf_proc = sp.Popen(  # noqa: S603,S602
                ["node", "-e", script],
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                text=True,
            )
            self._connected = True
            log.info("mineflayer 玩家模式已启动（真实玩家实体，26.1）")
            # 读 stdout，每行是一个聊天 JSON，回调 on_player_chat
            import threading

            def _read_chat() -> None:
                assert self._mf_proc is not None
                for line in self._mf_proc.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        import json

                        data = json.loads(line)
                        self.on_player_chat(data["user"], data["msg"])
                    except Exception as e:  # noqa: BLE001
                        log.debug("非 JSON 行: %s (%s)", line, e)

            threading.Thread(target=_read_chat, daemon=True).start()
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("mineflayer 连接失败，回退 RCON: %s", e)
            return False

    def connect(self) -> None:
        """连接到 MC 服务器（26.1 优先玩家模式，回退 RCON/桩）。

        1. mineflayer 真实玩家模式（26.1，需 Node.js + npm install mineflayer）
        2. RCON 后台模式（任意版本 26.2，需配 RCON 密码）
        3. 桩模式（不连服务器）
        """
        # 1. mineflayer 真实玩家模式（26.1）
        if self._try_mineflayer():
            self._poll_loop()
            return

        # 2. RCON 模式（支持 26.2 等任意版本，bot 是后台不是玩家实体）
        if self.rcon_password:
            try:
                from mcrcon import MCRcon  # type: ignore
            except ImportError:
                log.warning("mcrcon 未安装，bot 运行在桩模式")
                return

            log.info("RCON 连接 %s:%d", self.host, self.rcon_port)
            try:
                self._rcon = MCRcon(self.host, self.rcon_password, port=self.rcon_port)
                self._rcon.connect()
                self._connected = True
                log.info("RCON 已连接")
                self._refresh_state()
                self._poll_loop()
            except Exception as e:  # noqa: BLE001
                log.error("RCON 连接失败: %s", e)
                self._connected = False
            return

        # 3. 桩模式
        log.warning("未配置 mineflayer 或 RCON，bot 运行在桩模式")
        log.warning("装 Node.js + npm install mineflayer 启用玩家模式（26.1）")

    def _poll_loop(self, interval: float = 1.0) -> None:
        """轮询服务器日志监听聊天。

        RCON 本身是请求-响应模式，无法被动收消息。
        真实部署需读服务器 log 文件或用外部桥接（如 mineflayer + websocket）。
        这里用 /list 轮询作演示，实际聊天走 CLI 模式或日志桥接。
        """
        log.info("RCON 已连接，等待聊天指令（CLI 模式或日志桥接）")
        try:
            while self._connected:
                time.sleep(interval)
        except KeyboardInterrupt:
            self.disconnect()

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

    def disconnect(self) -> None:
        """断开连接（RCON 和 mineflayer 子进程都清理）。"""
        if self._mf_proc:
            try:
                self._mf_proc.terminate()
                self._mf_proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                pass
            self._mf_proc = None
        if self._rcon:
            try:
                self._rcon.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._connected = False
        log.info("已断开")


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
