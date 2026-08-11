"""插件发现、清单解析与进程内调用。"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

# v1 仅内置 5 个 API 插件
PLUGIN_IDS = [
    "deepseek-usage-plugin",
    "kimi-usage-plugin",
    "glm-usage-plugin",
    "minimax-usage-plugin",
    "ark-usage-plugin",
]

MANIFEST_BEGIN = "# UsageBoardPlugin:"
MANIFEST_END = "# /UsageBoardPlugin"

_modules: dict[str, Any] = {}
_manifests: dict[str, dict[str, Any]] = {}


def plugins_dir() -> Path:
    # PyInstaller onefile：资源解包到 sys._MEIPASS
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "plugins"
    # 开发环境：仓库内的单一来源
    return Path(__file__).resolve().parents[2] / "Resources" / "BundledPlugins"


def plugin_path(plugin_id: str) -> Path:
    return plugins_dir() / f"{plugin_id}.py"


def load_manifest(plugin_id: str) -> dict[str, Any]:
    if plugin_id in _manifests:
        return _manifests[plugin_id]
    path = plugin_path(plugin_id)
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index(MANIFEST_BEGIN)
        end = lines.index(MANIFEST_END)
    except ValueError:
        raise ValueError(f"插件缺少清单头: {path}")
    body = "\n".join(line[2:] if line.startswith("# ") else line.lstrip("#")
                     for line in lines[start + 1:end])
    manifest = json.loads(body)
    manifest["id"] = plugin_id
    _manifests[plugin_id] = manifest
    return manifest


def all_manifests() -> list[dict[str, Any]]:
    return [load_manifest(pid) for pid in PLUGIN_IDS if plugin_path(pid).exists()]


def localized(entry: dict[str, Any], key: str, language: str) -> str:
    value = entry.get(f"{key}@{language}") or entry.get(key) or ""
    return str(value)


def _load_module(plugin_id: str) -> Any:
    if plugin_id in _modules:
        return _modules[plugin_id]
    path = plugin_path(plugin_id)
    spec = importlib.util.spec_from_file_location(plugin_id.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载插件: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _modules[plugin_id] = module
    return module


def _error_message(plugin_id: str, exc: BaseException) -> str:
    detail = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()
    if len(detail) > 200:
        detail = detail[:200] + "…"
    return f"插件执行失败: {plugin_id}: {detail}"


def _log_failure(plugin_id: str) -> None:
    """把完整 traceback 追加到日志文件（windowed exe 没有控制台可看）。"""
    try:
        from datetime import datetime
        from .config import config_dir

        path = config_dir() / "usageboard.log"
        if path.exists() and path.stat().st_size > 1_000_000:
            # 简单轮转：只保留末尾约 400KB，避免长期失败把日志写爆
            tail = path.read_bytes()[-400_000:].decode("utf-8", errors="ignore")
            path.write_text(tail, encoding="utf-8")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"===== {datetime.now().isoformat(timespec='seconds')} [{plugin_id}] =====\n")
            traceback.print_exc(file=fh)
            fh.write("\n")
    except Exception:
        pass


def run_plugin(plugin_id: str, params: dict[str, str], language: str) -> dict[str, Any]:
    """进程内调用插件 run()，任何异常都收敛为 failure 字典。"""
    from .config import cache_dir

    merged = dict(params)
    merged["USAGEBOARD_LANGUAGE"] = language
    os.environ["USAGEBOARD_CACHE_DIR"] = str(cache_dir())
    try:
        module = _load_module(plugin_id)
        result = module.run(merged)
        if not isinstance(result, dict):
            return {"error": f"插件返回格式异常: {plugin_id}"}
        return result
    except Exception as exc:
        _log_failure(plugin_id)
        return {"error": _error_message(plugin_id, exc)}
