"""Minecraft 世界快照：订阅 chunk data，保存方块网格，支持查询。

世界以 chunk column（16x16x256 或 1.18+ 的 16x16x384）组织，
内部用扁平 dict 按 (x,y,z) 整数坐标存储方块，按需惰性解析。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# 空气方块的统一标识（无论命名空间变体）
_AIR = {"minecraft:air", "air", "0"}
# 判定为「实心可踩」的方块（简化：非空气即视为实心）
# 完整实现应查方块状态表，这里用排除列表
_PASSABLE = _AIR | {"minecraft:water", "minecraft:lava", "minecraft:snow", "minecraft:grass"}


@dataclass
class Block:
    """一个方块。"""
    x: int
    y: int
    z: int
    name: str  # 如 "minecraft:stone"

    def is_air(self) -> bool:
        return self.name in _AIR


class World:
    """方块世界快照。

    用法：
        world = World()
        world.set_chunk(...)
        block = world.get_block(10, 64, -5)
        found = world.find_blocks(("minecraft:oak_log",), (0, 64, 0), radius=16)
    """

    def __init__(self) -> None:
        # (x,y,z) -> block name
        self._blocks: dict[tuple[int, int, int], str] = {}

    def set_block(self, x: int, y: int, z: int, name: str) -> None:
        """更新一个方块。name 为 None/air 时移除。"""
        key = (x, y, z)
        if name is None or name in _AIR:
            self._blocks.pop(key, None)
        else:
            self._blocks[key] = name

    def get_block(self, x: int, y: int, z: int) -> Block:
        """查询方块。未知视为空气。"""
        name = self._blocks.get((x, y, z), "minecraft:air")
        return Block(x, y, z, name)

    def is_solid(self, x: int, y: int, z: int) -> bool:
        """方块是否实心（寻路用：非空气且非可穿过流体）。"""
        name = self._blocks.get((x, y, z))
        return name is not None and name not in _PASSABLE

    def is_walkable(self, x: int, y: int, z: int) -> bool:
        """该坐标是否可站立：脚下实心，身体与头部为空气。"""
        return (
            self.is_solid(x, y - 1, z)
            and not self.is_solid(x, y, z)
            and not self.is_solid(x, y + 1, z)
        )

    def find_blocks(
        self,
        names: tuple[str, ...],
        center: tuple[int, int, int],
        radius: int = 16,
        limit: int = 1,
    ) -> list[Block]:
        """在 center 附近 radius 球形范围内查找指定方块。

        返回按距离排序的 Block 列表，最多 limit 个。
        """
        cx, cy, cz = center
        r2 = radius * radius
        found: list[tuple[int, Block]] = []
        for (bx, by, bz), name in self._blocks.items():
            if name not in names:
                continue
            dx, dy, dz = bx - cx, by - cy, bz - cz
            if dx * dx + dy * dy + dz * dz > r2:
                continue
            dist = dx * dx + dy * dy + dz * dz
            found.append((dist, Block(bx, by, bz, name)))
        found.sort(key=lambda t: t[0])
        return [b for _, b in found[:limit]]

    def find_nearest_block(
        self,
        names: tuple[str, ...],
        center: tuple[int, int, int],
        radius: int = 16,
    ) -> Block | None:
        """查找最近的指定方块，无则返回 None。"""
        results = self.find_blocks(names, center, radius, limit=1)
        return results[0] if results else None

    def blocks_around(self, center: tuple[int, int, int], radius: int = 5) -> dict[str, int]:
        """统计周围方块类型与数量（look_around 用）。"""
        cx, cy, cz = center
        counts: dict[str, int] = {}
        for x in range(cx - radius, cx + radius + 1):
            for y in range(cy - radius, cy + radius + 1):
                for z in range(cz - radius, cz + radius + 1):
                    name = self._blocks.get((x, y, z))
                    if name and name not in _AIR:
                        counts[name] = counts.get(name, 0) + 1
        return counts

    def load_from_dict(self, blocks: dict[tuple[int, int, int], str]) -> None:
        """批量加载方块（测试/持久化用）。"""
        for pos, name in blocks.items():
            self.set_block(*pos, name)

    def size(self) -> int:
        """已存方块数（非空气）。"""
        return len(self._blocks)
