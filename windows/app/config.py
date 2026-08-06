"""配置读写：%APPDATA%/UsageBoard/config.json（可用 USAGEBOARD_CONFIG_DIR 覆盖）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

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
