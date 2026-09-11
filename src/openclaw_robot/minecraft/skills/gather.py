"""采集技能：导航到资源点并挖掘。

简化实现：根据当前坐标朝最近的目标方块走，挖到为止。
完整实现需要 A* 寻路 + 方块识别，这里给出框架。
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

# 资源 → 目标方块名映射（quarry 的 block name）
RESOURCE_BLOCKS = {
    "wood": ("minecraft:oak_log", "minecraft:birch_log"),
    "stone": ("minecraft:stone", "minecraft:cobblestone"),
    "coal": ("minecraft:coal_ore",),
    "iron": ("minecraft:iron_ore",),
    "diamond": ("minecraft:diamond_ore",),
}


def gather(bot: Any, resource: str, count: int = 1) -> str:
    """采集指定资源。

    bot: MinecraftBot 实例
    resource: wood/stone/coal/iron/diamond
    count: 目标数量
    """
    resource = resource.lower()
    targets = RESOURCE_BLOCKS.get(resource)
    if not targets:
        return f"未知资源: {resource}，可选: {list(RESOURCE_BLOCKS)}"

    log.info("开始采集 %s x%d", resource, count)
    found = 0
    attempts = 0
    max_attempts = count * 10 + 20

    while found < count and attempts < max_attempts:
        attempts += 1
        # 扫描周围 16 格内是否有目标方块
        block = bot.find_nearest_block(targets, radius=16)
        if block is None:
            bot.chat(f"附近没找到 {resource}，先去别处看看")
            time.sleep(0.5)
            continue

        # 走过去（简化：直接传送附近，实际应寻路）
        if not bot.move_near(block.position):
            continue

        # 挖掘
        if bot.dig_block(block.position):
            found += 1
            log.info("挖到 %s (%d/%d)", resource, found, count)

    if found < count:
        return f"只采到 {found}/{count} 个 {resource}（附近资源不足）"
    return f"采集完成：{count} 个 {resource}"


# 用于注册到 ToolRegistry 的函数签名
def gather_tool(resource: str, count: int = 1) -> str:
    """采集资源。resource: wood/stone/coal/iron/diamond。"""
    # 实际执行由 bot 注入 self 后调用 gather(bot, ...)
    # 这里只是签名占位，真实调用见 bot.py 的 _make_tools
    return f"（采集 {resource} x{count}：需通过 bot 实例执行）"
