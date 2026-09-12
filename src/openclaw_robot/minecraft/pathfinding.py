"""A* 寻路器：在 3D 方块网格上找可通行路径。

可通行判定：脚下实心、身体与头部为空气（站立空间）。
邻居：上下左右 + 跳跃（+1 层）+ 下落（-多 层）。
"""

from __future__ import annotations

import heapq
import logging
from collections.abc import Callable
from dataclasses import dataclass

from .world import World

log = logging.getLogger(__name__)

# 6 个水平/垂直邻居
_NEIGHBORS = [
    (1, 0, 0), (-1, 0, 0),
    (0, 0, 1), (0, 0, -1),
]
# 最大下落距离（直接掉下去不算路径）
_MAX_DROP = 3
# 最大跳跃高度
_MAX_JUMP = 1


@dataclass
class PathResult:
    """寻路结果。"""
    path: list[tuple[int, int, int]]
    length: int
    success: bool

    def __bool__(self) -> bool:
        return self.success


def heuristic(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """3D 欧几里得距离启发式。"""
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def find_path(
    world: World,
    start: tuple[int, int, int],
    goal: tuple[int, int, int],
    max_steps: int = 1000,
    is_walkable: Callable[[World, int, int, int], bool] | None = None,
) -> PathResult:
    """A* 寻路。

    start/goal: (x, y, z) 整数坐标
    返回 PathResult，path 为坐标列表（含起点），失败时 success=False。
    """
    _walkable = is_walkable or (lambda w, x, y, z: w.is_walkable(x, y, z))

    # 起点必须可站立（否则无法出发）
    if not _walkable(world, *start):
        # 容错：从起点正下方找支撑
        log.debug("起点 %s 不可站立，尝试向下找地面", start)

    open_heap: list[tuple[float, int, tuple[int, int, int]]] = []
    counter = 0
    heapq.heappush(open_heap, (heuristic(start, goal), counter, start))
    came_from: dict[tuple[int, int, int], tuple[int, int, int] | None] = {start: None}
    g_score: dict[tuple[int, int, int], float] = {start: 0.0}
    steps = 0

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        steps += 1
        if steps > max_steps:
            log.debug("寻路超过最大步数 %d", max_steps)
            break

        if current == goal:
            # 重建路径
            path = []
            node: tuple[int, int, int] | None = current
            while node is not None:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return PathResult(path=path, length=len(path), success=True)

        for neighbor in _expand(world, current, _walkable):
            tentative = g_score[current] + 1.0
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                f = tentative + heuristic(neighbor, goal)
                counter += 1
                heapq.heappush(open_heap, (f, counter, neighbor))

    return PathResult(path=[], length=0, success=False)


def _expand(
    world: World,
    pos: tuple[int, int, int],
    is_walkable: Callable[[World, int, int, int], bool],
) -> list[tuple[int, int, int]]:
    """展开当前节点的可通行邻居。

    支持：平移、跳跃（上1层）、下落（下至3层）。
    每个候选落脚点必须可站立。
    """
    x, y, z = pos
    result: list[tuple[int, int, int]] = []

    for dx, _, dz in _NEIGHBORS:
        nx, nz = x + dx, z + dz

        # 1. 平移（同层）
        if is_walkable(world, nx, y, nz):
            result.append((nx, y, nz))
            continue

        # 2. 跳跃（上方有空间且前方可站立 +1）
        if is_walkable(world, nx, y + _MAX_JUMP, nz) and not world.is_solid(x, y + 1, z):
            result.append((nx, y + _MAX_JUMP, nz))

        # 3. 下落（向下找可站立点）
        for drop in range(1, _MAX_DROP + 1):
            ty = y - drop
            if is_walkable(world, nx, ty, nz):
                result.append((nx, ty, nz))
                break
            # 下落途中若碰到实心方块，此列不可下落
            if world.is_solid(nx, ty + 1, nz) and not is_walkable(world, nx, ty, nz):
                break

    return result
