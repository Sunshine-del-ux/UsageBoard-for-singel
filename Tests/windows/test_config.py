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


# ─── 多账号实例 ──────────────────────────────────────────────────────────────


def test_instances_default_empty(tmp_path):
    config = make_config(tmp_path)
    assert config.plugin_instances() == []
    assert config.plugin_instances("deepseek-usage-plugin") == []


def test_add_instance_roundtrip(tmp_path):
    config = make_config(tmp_path)
    inst = config.add_instance("deepseek-usage-plugin", "账号 2")
    assert inst["type"] == "deepseek-usage-plugin"
    assert inst["name"] == "账号 2"
    assert inst["id"].startswith("deepseek-usage-plugin@")
    assert inst["params"] == {}

    config.set_instance_params(inst["id"], {"API_KEY": "sk-second"})
    config.save()

    loaded = make_config(tmp_path)
    instances = loaded.plugin_instances("deepseek-usage-plugin")
    assert len(instances) == 1
    assert instances[0]["id"] == inst["id"]
    assert instances[0]["name"] == "账号 2"
    assert loaded.instance_params(inst["id"]) == {"API_KEY": "sk-second"}


def test_instances_filtered_by_type(tmp_path):
    config = make_config(tmp_path)
    config.add_instance("deepseek-usage-plugin", "A")
    config.add_instance("kimi-usage-plugin", "B")
    assert len(config.plugin_instances()) == 2
    only = config.plugin_instances("kimi-usage-plugin")
    assert len(only) == 1
    assert only[0]["type"] == "kimi-usage-plugin"


def test_rename_instance(tmp_path):
    config = make_config(tmp_path)
    inst = config.add_instance("glm-usage-plugin", "旧名")
    config.rename_instance(inst["id"], "新名")
    assert config.plugin_instances("glm-usage-plugin")[0]["name"] == "新名"
    config.rename_instance("glm-usage-plugin@missing", "无名")  # 不存在不报错


def test_remove_instance(tmp_path):
    config = make_config(tmp_path)
    first = config.add_instance("deepseek-usage-plugin", "A")
    second = config.add_instance("deepseek-usage-plugin", "B")
    config.remove_instance(first["id"])
    remaining = config.plugin_instances("deepseek-usage-plugin")
    assert [inst["id"] for inst in remaining] == [second["id"]]
    # 删除后实例参数查询安全返回空
    assert config.instance_params(first["id"]) == {}


def test_malformed_instances_ignored(tmp_path):
    config = make_config(tmp_path, {"instances": "not-a-list"})
    assert config.plugin_instances() == []
    config = make_config(tmp_path, {"instances": [
        "junk",
        {"type": "x"},                       # 缺 id
        {"id": "y"},                         # 缺 type
        {"id": "x@1", "type": "x", "params": {"N": 5}},
    ]})
    instances = config.plugin_instances()
    assert len(instances) == 1
    assert instances[0]["params"] == {"N": "5"}
