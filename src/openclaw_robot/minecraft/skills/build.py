"""建造技能：按结构名在指定坐标放置方块。"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

# 预定义结构（相对坐标 → 方块）
STRUCTURES: dict[str, list[tuple[tuple[int, int, int], str]]] = {
    "hut": [
        # 4x4 木屋，3 高
        ([(x, 0, z) for x in range(4) for z in range(4)] * 1, "minecraft:oak_planks"),
    ],
    "tower": [
        ([(0, y, 0) for y in range(6)], "minecraft:cobblestone"),
    ],
    "torch": [
        ([(0, 0, 0)], "minecraft:torch"),
    ],
}


def _flatten(structure):
    """把 STRUCTURES 的混合格式展开成 [(pos, block)] 列表。"""
    result = []
    for positions, block in structure:
        for pos in positions:
            result.append((pos, block))
    return result


def build(bot: Any, structure: str, x: float, y: float, z: float) -> str:
    """在 (x,y,z) 处建造结构。

    structure: 预定义结构名（hut/tower/torch）
    """
    structure = structure.lower()
    if structure not in STRUCTURES:
        return f"未知结构: {structure}，可选: {list(STRUCTURES)}"

    blocks = _flatten(STRUCTURES[structure])
    log.info("在 (%.0f,%.0f,%.0f) 建造 %s，共 %d 个方块", x, y, z, structure, len(blocks))

    placed = 0
    for (dx, dy, dz), block in blocks:
        pos = (int(x) + dx, int(y) + dy, int(z) + dz)
        if bot.place_block(pos, block):
            placed += 1
            time.sleep(0.2)  # 避免发包过快
        else:
            log.warning("放置失败 %s @ %s", block, pos)

    return f"建造完成：{structure} ({placed}/{len(blocks)} 个方块)"


def build_tool(structure: str, x: float, y: float, z: float) -> str:
    """建造结构。structure: hut/tower/torch，坐标 (x,y,z)。"""
    return build_tool(structure, x, y, z)
