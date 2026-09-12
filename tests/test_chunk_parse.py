"""MC chunk 解析测试：验证 _parse_chunk 能从 palette + packed data 还原方块。"""

from openclaw_robot.minecraft.bot import _ceil_log2, _parse_chunk, _unpack_packed
from openclaw_robot.minecraft.world import World


def test_ceil_log2():
    assert _ceil_log2(1) == 0
    assert _ceil_log2(2) == 1
    assert _ceil_log2(3) == 2
    assert _ceil_log2(4) == 2
    assert _ceil_log2(5) == 3
    assert _ceil_log2(16) == 4


def test_unpack_packed_basic():
    """4 位/值，每个 long 装 16 个值。"""
    # long0 = 0x10 → 第 1 个值 = 1，其余 0
    states = _unpack_packed([0x10], 4, 16)
    assert len(states) == 16
    assert states[0] == 0
    assert states[1] == 1
    assert states[2] == 0


def test_unpack_packed_values_per_long():
    """bits_per 不整除 64 时，每个 long 装 floor(64/bits_per) 个值。"""
    # 5 位/值 → 每个 long 装 12 个值（剩余 4 位忽略）
    # 第 13 个值从第二个 long 的最低位取
    states = _unpack_packed([0xFFFFFFFFFFFFFFFF, 0x1], 5, 13)
    assert states[0] == 31
    assert states[11] == 31  # 第一个 long 的最后一个值
    assert states[12] == 1   # 第二个 long 的第一个值


def test_unpack_packed_pads_short_data():
    """数据不足时补 0。"""
    states = _unpack_packed([], 4, 8)
    assert states == [0] * 8


def test_parse_chunk_writes_blocks_to_world():
    """palette + packed data 解析后，对应坐标写入 world。"""
    world = World()
    palette = ["minecraft:air", "minecraft:stone"]
    # 索引 33 = local(1, 0, 2)，设为 stone (palette[1])
    # bits_per=4, 每个 long 16 个值，索引 33 在 long2 的位置 1
    data = {
        "chunk_x": 0,
        "chunk_z": 0,
        "sections": [{"palette": palette, "data": [0, 0, 0x10]}],
    }
    _parse_chunk(world, data)

    # (1, 0, 2) 应该是 stone
    assert world.get_block(1, 0, 2).name == "minecraft:stone"
    # 其他位置是 air（不存）
    assert world.get_block(0, 0, 0).is_air()
    assert world.size() == 1


def test_parse_chunk_air_not_stored():
    """空气方块不写入 world（size 不变）。"""
    world = World()
    palette = ["minecraft:air"]  # 只有空气
    data = {
        "chunk_x": 0,
        "chunk_z": 0,
        "sections": [{"palette": palette, "data": [0] * 16}],
    }
    _parse_chunk(world, data)
    assert world.size() == 0


def test_parse_chunk_dict_palette_entries():
    """palette 条目是 {"name": ...} 字典形式时也能解析。"""
    world = World()
    palette = [{"name": "minecraft:air"}, {"name": "minecraft:oak_log"}]
    data = {
        "chunk_x": 2,  # 全局 x = 2*16 + local_x
        "chunk_z": 3,  # 全局 z = 3*16 + local_z
        "sections": [{"palette": palette, "data": [0, 0, 0x10]}],
    }
    _parse_chunk(world, data)
    # 索引 33 → local(1,0,2) → 全局 (2*16+1, 0, 3*16+2) = (33, 0, 50)
    assert world.get_block(33, 0, 50).name == "minecraft:oak_log"


def test_parse_chunk_missing_fields_skipped():
    """缺少 palette 或 data 时静默跳过，不抛异常。"""
    world = World()
    _parse_chunk(world, {"sections": [{}]})
    _parse_chunk(world, {"sections": [{"palette": ["minecraft:stone"]}]})
    _parse_chunk(world, {})
    assert world.size() == 0


def test_parse_chunk_full_section_solid():
    """整个 section 都是石头：验证 4096 个方块都被写入。"""
    world = World()
    palette = ["minecraft:stone"]
    # 4096 个值，每个 4 位 → 4096*4/64 = 256 个 long
    longs = [0] * 256
    data = {
        "chunk_x": 0,
        "chunk_z": 0,
        "sections": [{"palette": palette, "data": longs}],
    }
    _parse_chunk(world, data)
    assert world.size() == 4096
