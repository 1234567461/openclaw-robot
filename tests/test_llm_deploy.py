"""LLM 部署适配测试：预设工厂、is_local 判定、错误处理。

覆盖本地（Ollama/vLLM）与云端（OpenAI/DeepSeek/SiliconFlow）切换。
"""

import pytest

from openclaw_robot.core.llm import LLM, PRESETS


def test_presets_cover_local_and_cloud_backends():
    """预设覆盖常见本地与云端后端。"""
    assert {"openai", "deepseek", "ollama", "vllm", "siliconflow"} <= set(PRESETS)
    # 本地后端的 api_base 是 localhost
    assert "localhost" in PRESETS["ollama"]["api_base"]
    assert "localhost" in PRESETS["vllm"]["api_base"]
    # 云端后端的 api_base 是 https
    assert PRESETS["openai"]["api_base"].startswith("https://")
    assert PRESETS["deepseek"]["api_base"].startswith("https://")


def test_create_local_preset_supplies_default_key():
    """本地后端用预设的占位 key，省去用户配置。"""
    llm = LLM.create("ollama")
    assert llm.api_key == "ollama"
    assert llm.is_local
    assert llm.model == "qwen2.5:7b"


def test_create_vllm_preset():
    llm = LLM.create("vllm")
    assert llm.api_key == "EMPTY"
    assert llm.is_local


def test_create_cloud_preset_uses_supplied_key():
    """云端后端必须由用户提供真实 key。"""
    llm = LLM.create("openai", api_key="sk-real")
    assert not llm.is_local
    assert llm.api_key == "sk-real"


def test_create_overrides_model_and_key():
    """create 的显式参数覆盖预设。"""
    llm = LLM.create("ollama", api_key="custom", model="llama3:8b")
    assert llm.api_key == "custom"
    assert llm.model == "llama3:8b"


def test_create_unknown_preset_raises():
    with pytest.raises(ValueError, match="未知预设"):
        LLM.create("nonexistent")


def test_llm_init_requires_api_key(monkeypatch):
    """无 api_key 且环境变量未设置时报错。"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        LLM()


def test_llm_is_local_detection():
    assert LLM(api_base="http://127.0.0.1:11434/v1", api_key="x").is_local
    assert LLM(api_base="http://localhost:8000/v1", api_key="x").is_local
    assert not LLM(api_base="https://api.openai.com/v1", api_key="x").is_local
    assert not LLM(api_base="https://api.deepseek.com", api_key="x").is_local


def test_llm_env_var_config(monkeypatch):
    """通过环境变量配置云端后端。"""
    monkeypatch.setenv("LLM_API_BASE", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "sk-ds")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    llm = LLM()
    assert llm.api_base == "https://api.deepseek.com"
    assert llm.api_key == "sk-ds"
    assert llm.model == "deepseek-chat"
    assert not llm.is_local


def test_local_backend_no_key_autofill(monkeypatch):
    """本地后端（Ollama/vLLM）即使没配 LLM_API_KEY 也能用，自动填占位 key。"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_BASE", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    llm = LLM()
    assert llm.is_local
    assert llm.api_key == "local"  # 自动填的占位，无需用户手动配


def test_local_backend_127_autofill():
    """127.0.0.1 也算本地，自动填占位 key。"""
    llm = LLM(api_base="http://127.0.0.1:8000/v1", model="qwen2.5-7b")
    assert llm.is_local
    assert llm.api_key == "local"


def test_cloud_backend_no_key_still_raises(monkeypatch):
    """云端后端没配 key 仍报错（保护用户，避免白跑）。"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_BASE", "https://api.openai.com/v1")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        LLM()
