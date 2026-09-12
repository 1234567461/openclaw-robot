"""A* 寻路器测试。"""

from openclaw_robot.minecraft.pathfinding import find_path
from openclaw_robot.minecraft.world import World


def test_pathfind_straight_line():
    """平地直线：起点到终点中间全是实心地面，上方空气。"""
    w = World()
    # 铺一条 x=0..4 的地面，y=62 为石头，y=63/64 为空气
    for x in range(5):
        w.set_block(x, 62, 0, "minecraft:stone")
    result = find_path(w, (0, 63, 0), (4, 63, 0))
    assert result.success
    assert len(result.path) == 5  # 5 个格子
    assert result.path[0] == (0, 63, 0)
    assert result.path[-1] == (4, 63, 0)


def test_pathfind_blocked_no_path():
    """终点被堵死（四周实心）→ 寻路失败。"""
    w = World()
    for x in range(3):
        for y in range(4):
            w.set_block(x, 60 + y, 0, "minecraft:stone")
    result = find_path(w, (0, 60, 5), (1, 62, 0), max_steps=50)
    # 起点不可站立，终点也被封
    assert not result.success


def test_pathfind_short_distance():
    """相邻一格。"""
    w = World()
    w.set_block(0, 62, 0, "minecraft:stone")
    w.set_block(1, 62, 0, "minecraft:stone")
    result = find_path(w, (0, 63, 0), (1, 63, 0))
    assert result.success
    assert len(result.path) == 2


def test_pathfind_same_point():
    """起点=终点。"""
    w = World()
    w.set_block(0, 62, 0, "minecraft:stone")
    result = find_path(w, (0, 63, 0), (0, 63, 0))
    assert result.success
    assert len(result.path) == 1


def test_pathfind_jump_up():
    """跳跃上一层：目标高1格，前方可站。"""
    w = World()
    # 低层地面
    w.set_block(0, 62, 0, "minecraft:stone")
    w.set_block(1, 62, 0, "minecraft:stone")
    # 高一层地面
    w.set_block(1, 63, 0, "minecraft:stone")
    result = find_path(w, (0, 63, 0), (1, 64, 0))
    assert result.success
    assert result.path[-1] == (1, 64, 0)


def test_pathfind_max_steps_limit():
    """超过最大步数。"""
    w = World()
    for x in range(100):
        w.set_block(x, 62, 0, "minecraft:stone")
    result = find_path(w, (0, 63, 0), (99, 63, 0), max_steps=10)
    assert not result.success
