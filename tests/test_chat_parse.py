"""chat JSON 组件解析测试。"""

from openclaw_robot.minecraft.bot import _extract_text


def test_extract_plain_string():
    assert _extract_text("hello") == "hello"


def test_extract_dict_with_text():
    assert _extract_text({"text": "你好"}) == "你好"


def test_extract_dict_with_extra():
    comp = {"text": "", "extra": [{"text": "Player"}, {"text": "> hi"}]}
    assert _extract_text(comp) == "Player> hi"


def test_extract_list():
    assert _extract_text([{"text": "A"}, "B", {"text": "C"}]) == "ABC"


def test_extract_empty():
    assert _extract_text({}) == ""
    assert _extract_text(None) == ""
