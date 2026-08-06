"""windows/app/config.py 的单元测试。"""
from __future__ import annotations

import json

from windows.app.config import Config, DEFAULT_REFRESH_INTERVAL_SEC


def make_config(tmp_path, initial: dict | None = None) -> Config:
    path = tmp_path / "config.json"
    if initial is not None:
        path.write_text(json.dumps(initial), encoding="utf-8")
    return Config(path)


def test_defaults_when_file_missing(tmp_path):
    config = make_config(tmp_path)
    assert config.language is None
    assert config.refresh_interval_sec == DEFAULT_REFRESH_INTERVAL_SEC
    assert config.plugin_enabled("deepseek-usage-plugin") is True
    assert config.plugin_params("deepseek-usage-plugin") == {}


def test_roundtrip(tmp_path):
    config = make_config(tmp_path)
    config.language = "en"
    config.refresh_interval_sec = 120
    config.set_plugin_enabled("kimi-usage-plugin", False)
    config.set_plugin_params("deepseek-usage-plugin", {"API_KEY": "sk-test", "LIMIT": "50"})
    config.save()

    loaded = make_config(tmp_path)
    assert loaded.language == "en"
    assert loaded.refresh_interval_sec == 120
    assert loaded.plugin_enabled("kimi-usage-plugin") is False
    assert loaded.plugin_params("deepseek-usage-plugin") == {"API_KEY": "sk-test", "LIMIT": "50"}


def test_invalid_language_falls_back_to_none(tmp_path):
    config = make_config(tmp_path, {"language": "fr"})
    assert config.language is None


def test_refresh_interval_floor(tmp_path):
    config = make_config(tmp_path, {"refreshIntervalSec": 5})
    assert config.refresh_interval_sec == 30
    config = make_config(tmp_path, {"refreshIntervalSec": "abc"})
    assert config.refresh_interval_sec == DEFAULT_REFRESH_INTERVAL_SEC


def test_corrupt_file_uses_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    config = Config(path)
    assert config.language is None


def test_params_coerced_to_str(tmp_path):
    config = make_config(tmp_path, {"plugins": {"x": {"params": {"LIMIT": 100}}}})
    assert config.plugin_params("x") == {"LIMIT": "100"}
