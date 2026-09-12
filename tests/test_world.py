"""World 世界快照测试。"""

from openclaw_robot.minecraft.world import World


def test_world_set_get_block():
    w = World()
    w.set_block(10, 64, -5, "minecraft:stone")
    b = w.get_block(10, 64, -5)
    assert b.name == "minecraft:stone"
    assert not b.is_air()


def test_world_air_is_default():
    w = World()
    b = w.get_block(0, 0, 0)
    assert b.is_air()
    assert b.name == "minecraft:air"


def test_world_set_air_removes():
    w = World()
    w.set_block(1, 1, 1, "minecraft:dirt")
    w.set_block(1, 1, 1, "minecraft:air")
    assert w.get_block(1, 1, 1).is_air()
    assert w.size() == 0


def test_world_is_solid():
    w = World()
    w.set_block(5, 63, 5, "minecraft:stone")
    assert w.is_solid(5, 63, 5)
    assert not w.is_solid(5, 64, 5)  # 空气
    assert not w.is_solid(5, 63, 6)  # 未设置=空气


def test_world_is_walkable():
    w = World()
    # 脚下石头，身体+头部空气 → 可站立
    w.set_block(0, 62, 0, "minecraft:stone")
    assert w.is_walkable(0, 63, 0)
    # 身体被堵 → 不可站
    w.set_block(0, 63, 0, "minecraft:dirt")
    assert not w.is_walkable(0, 63, 0)


def test_world_find_nearest_block():
    w = World()
    w.set_block(3, 64, 0, "minecraft:oak_log")
    w.set_block(5, 64, 0, "minecraft:oak_log")
    w.set_block(10, 64, 0, "minecraft:stone")
    # 从原点找橡木
    found = w.find_nearest_block(("minecraft:oak_log",), (0, 64, 0), radius=16)
    assert found is not None
    assert found.name == "minecraft:oak_log"
    assert found.x == 3  # 最近的


def test_world_find_blocks_limit():
    w = World()
    for x in range(5):
        w.set_block(x, 0, 0, "minecraft:coal_ore")
    results = w.find_blocks(("minecraft:coal_ore",), (0, 0, 0), radius=10, limit=2)
    assert len(results) == 2
    # 按距离排序，最近的是 x=0
    assert results[0].x == 0


def test_world_blocks_around():
    w = World()
    w.set_block(0, 0, 0, "minecraft:stone")
    w.set_block(1, 0, 0, "minecraft:stone")
    w.set_block(0, 0, 1, "minecraft:dirt")
    counts = w.blocks_around((0, 0, 0), radius=1)
    assert counts["minecraft:stone"] == 2
    assert counts["minecraft:dirt"] == 1


def test_world_water_is_passable():
    w = World()
    w.set_block(0, 60, 0, "minecraft:water")
    assert not w.is_solid(0, 60, 0)
