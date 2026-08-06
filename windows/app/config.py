"""配置读写：%APPDATA%/UsageBoard/config.json（可用 USAGEBOARD_CONFIG_DIR 覆盖）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

APP_NAME = "UsageBoard"
DEFAULT_REFRESH_INTERVAL_SEC = 300


def config_dir() -> Path:
    override = os.environ.get("USAGEBOARD_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    # 开发环境（macOS/Linux）
    return Path.home() / ".config" / APP_NAME


def cache_dir() -> Path:
    return config_dir() / "plugin-caches"


DEFAULT_CONFIG: dict[str, Any] = {
    "language": None,  # None = 跟随系统
    "refreshIntervalSec": DEFAULT_REFRESH_INTERVAL_SEC,
    "plugins": {},
    "instances": [],  # 同类型插件的额外账号实例
}


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / "config.json")
        self.data: dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key == "plugins" and isinstance(value, dict):
                    self.data["plugins"].update(value)
                elif key in self.data:
                    self.data[key] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ─── 便捷访问 ─────────────────────────────────────────────────────────────

    @property
    def language(self) -> str | None:
        value = self.data.get("language")
        return value if value in ("zh-Hans", "en") else None

    @language.setter
    def language(self, value: str | None) -> None:
        self.data["language"] = value if value in ("zh-Hans", "en") else None

    @property
    def refresh_interval_sec(self) -> int:
        try:
            value = int(self.data.get("refreshIntervalSec", DEFAULT_REFRESH_INTERVAL_SEC))
        except (TypeError, ValueError):
            return DEFAULT_REFRESH_INTERVAL_SEC
        return max(30, value)

    @refresh_interval_sec.setter
    def refresh_interval_sec(self, value: int) -> None:
        self.data["refreshIntervalSec"] = max(30, int(value))

    def plugin_enabled(self, plugin_id: str) -> bool:
        entry = self.data["plugins"].get(plugin_id)
        if entry is None:
            return True  # 默认启用
        return bool(entry.get("enabled", True))

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        entry = self.data["plugins"].setdefault(plugin_id, {})
        entry["enabled"] = bool(enabled)

    def plugin_params(self, plugin_id: str) -> dict[str, str]:
        entry = self.data["plugins"].get(plugin_id) or {}
        params = entry.get("params") or {}
        return {str(k): str(v) for k, v in params.items()}

    def set_plugin_params(self, plugin_id: str, params: dict[str, str]) -> None:
        entry = self.data["plugins"].setdefault(plugin_id, {})
        entry["params"] = {str(k): str(v) for k, v in params.items()}

    # ─── 插件多账号（同类型额外实例） ────────────────────────────────────────

    def plugin_instances(self, plugin_type: str | None = None) -> list[dict[str, Any]]:
        """额外账号实例列表，每项 {id, type, name, params}。"""
        instances = self.data.get("instances")
        if not isinstance(instances, list):
            return []
        result: list[dict[str, Any]] = []
        for item in instances:
            if not isinstance(item, dict):
                continue
            itype = str(item.get("type") or "")
            iid = str(item.get("id") or "")
            if not itype or not iid:
                continue
            if plugin_type is not None and itype != plugin_type:
                continue
            params = item.get("params") or {}
            result.append({
                "id": iid,
                "type": itype,
                "name": str(item.get("name") or ""),
                "params": {str(k): str(v) for k, v in params.items()},
            })
        return result

    def add_instance(self, plugin_type: str, name: str = "") -> dict[str, Any]:
        instance = {
            "id": f"{plugin_type}@{uuid4().hex[:6]}",
            "type": plugin_type,
            "name": name,
            "params": {},
        }
        instances = self.data.setdefault("instances", [])
        if not isinstance(instances, list):
            instances = []
            self.data["instances"] = instances
        instances.append(instance)
        return dict(instance)

    def remove_instance(self, instance_id: str) -> None:
        instances = self.data.get("instances")
        if isinstance(instances, list):
            self.data["instances"] = [
                item for item in instances
                if not (isinstance(item, dict) and item.get("id") == instance_id)
            ]

    def _find_instance(self, instance_id: str) -> dict[str, Any] | None:
        instances = self.data.get("instances")
        if not isinstance(instances, list):
            return None
        for item in instances:
            if isinstance(item, dict) and item.get("id") == instance_id:
                return item
        return None

    def rename_instance(self, instance_id: str, name: str) -> None:
        item = self._find_instance(instance_id)
        if item is not None:
            item["name"] = name

    def instance_params(self, instance_id: str) -> dict[str, str]:
        item = self._find_instance(instance_id)
        params = (item or {}).get("params") or {}
        return {str(k): str(v) for k, v in params.items()}

    def set_instance_params(self, instance_id: str, params: dict[str, str]) -> None:
        item = self._find_instance(instance_id)
        if item is not None:
            item["params"] = {str(k): str(v) for k, v in params.items()}
