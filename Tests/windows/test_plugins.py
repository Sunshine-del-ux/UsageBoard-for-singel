"""windows/app/plugins.py 的单元测试。"""
from __future__ import annotations

import pytest

from windows.app.plugins import (
    PLUGIN_IDS, all_manifests, load_manifest, localized, plugin_path, run_plugin,
)


def test_all_four_plugins_present():
    for plugin_id in PLUGIN_IDS:
        assert plugin_path(plugin_id).exists(), plugin_id


def test_manifests_parse_and_have_parameters():
    manifests = all_manifests()
    assert len(manifests) == 4
    for manifest in manifests:
        assert manifest["schemaVersion"] == 1
        assert manifest["name"]
        assert manifest["id"].endswith("-usage-plugin")
        param_names = [p["name"] for p in manifest.get("parameters", [])]
        assert "API_KEY" in param_names, manifest["id"]


def test_manifest_cached():
    first = load_manifest("deepseek-usage-plugin")
    second = load_manifest("deepseek-usage-plugin")
    assert first is second


def test_localized_fallback():
    manifest = load_manifest("deepseek-usage-plugin")
    assert localized(manifest, "name", "zh-Hans") == "DeepSeek"
    assert localized(manifest, "name", "en") == "DeepSeek"
    glm = load_manifest("glm-usage-plugin")
    assert localized(glm, "name", "en") == "Zhipu"
    assert localized(glm, "name", "zh-Hans") == "智谱"


@pytest.mark.parametrize("plugin_id", PLUGIN_IDS)
def test_run_plugin_missing_api_key_returns_error(plugin_id, monkeypatch, tmp_path):
    monkeypatch.setenv("USAGEBOARD_CONFIG_DIR", str(tmp_path))
    result = run_plugin(plugin_id, {}, "zh-Hans")
    assert isinstance(result, dict)
    assert "error" in result
    result_en = run_plugin(plugin_id, {}, "en")
    assert "error" in result_en
    assert result["error"] != result_en["error"] or plugin_id == "deepseek-usage-plugin"


def test_run_plugin_injects_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGEBOARD_CONFIG_DIR", str(tmp_path))
    run_plugin("glm-usage-plugin", {}, "zh-Hans")
    import os
    assert os.environ["USAGEBOARD_CACHE_DIR"] == str(tmp_path / "plugin-caches")
