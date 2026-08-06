"""windows/app/i18n.py 与 worker.py 的单元测试。"""
from __future__ import annotations

from windows.app import i18n


def test_tr_both_languages():
    i18n.set_language("zh-Hans")
    assert i18n.tr("settings") == "设置"
    i18n.set_language("en")
    assert i18n.tr("settings") == "Settings"


def test_tr_format_kwargs():
    i18n.set_language("zh-Hans")
    assert i18n.tr("usage_of", used="1", limit="10") == "1 / 10"


def test_tr_unknown_key_returns_key():
    assert i18n.tr("no_such_key") == "no_such_key"


def test_set_language_invalid_falls_back():
    i18n.set_language("fr")
    assert i18n.language() == "zh-Hans"
    i18n.set_language("zh-Hans")


def test_worker_job_runs_plugin_synchronously(tmp_path, monkeypatch):
    pytest = __import__("pytest")
    pytest.importorskip("PySide6")
    monkeypatch.setenv("USAGEBOARD_CONFIG_DIR", str(tmp_path))

    from windows.app.worker import RefreshJob

    results: list[tuple[str, dict]] = []
    job = RefreshJob("deepseek-usage-plugin", {}, "zh-Hans",
                     lambda pid, res: results.append((pid, res)))
    job.run()  # 同步执行，不经过线程池
    assert len(results) == 1
    plugin_id, result = results[0]
    assert plugin_id == "deepseek-usage-plugin"
    assert "error" in result  # 未配置 API_KEY
