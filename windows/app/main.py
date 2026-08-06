"""入口：QApplication + 托盘 + 面板 + 定时刷新。"""
from __future__ import annotations

import copy
import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from . import i18n, theme
from .config import Config, config_dir
from .panel import Panel
from .plugins import all_manifests, localized
from .settings import SettingsDialog
from .tray import Tray
from .worker import WorkerPool


def _apply_theme(app: QApplication) -> None:
    """Fusion + macOS 浅色主题，并指定接近 San Francisco 观感的字体。"""
    theme.apply_palette(app)
    families = ["Segoe UI Variable Text", "Segoe UI"] if sys.platform == "win32" \
        else [".AppleSystemUIFont", "Helvetica Neue"]
    font = QFont(families[0], 9)
    font.setFamilies(families)
    app.setFont(font)


class UsageBoardApp:
    def __init__(self):
        # 单实例锁：防止多个 exe 同时运行（旧实例的面板不受新托盘图标控制）
        config_dir().mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(config_dir() / "usageboard.lock"))
        self._lock.setStaleLockTime(0)  # 立即识别崩溃残留的锁
        if not self._lock.tryLock(100):
            raise SystemExit(0)

        self._qt = QApplication(sys.argv)
        self._qt.setQuitOnLastWindowClosed(False)
        self._qt.setApplicationName("UsageBoard")
        _apply_theme(self._qt)

        icon = QIcon(str(theme.app_icon_path()))
        self._qt.setWindowIcon(icon)

        self._config = Config()
        language = self._config.language or i18n.system_language()
        i18n.set_language(language)

        self._manifests = all_manifests()
        self._panel = Panel()
        self._rebuild_cards()

        self._pool = WorkerPool(self._on_result)

        self._tray = Tray(icon)
        self._tray.show_panel_requested.connect(self._panel.toggle_near)
        self._tray.refresh_requested.connect(self.refresh_all)
        self._tray.settings_requested.connect(self.open_settings)
        self._tray.quit_requested.connect(self._quit)
        self._tray.show()

        self._panel.refresh_requested.connect(self.refresh_all)
        self._panel.settings_requested.connect(self.open_settings)
        self._panel.quit_requested.connect(self._quit)

        self._timer = QTimer(self._qt)
        self._timer.timeout.connect(self.refresh_all)
        self._timer.start(self._config.refresh_interval_sec * 1000)

        self._pending: set[str] = set()
        QTimer.singleShot(300, self.refresh_all)

    # ─── 刷新 ───

    def _effective_manifests(self) -> list[dict]:
        """启用插件的默认清单 + 额外账号实例的合成清单（卡片 id = 实例 id）。"""
        effective: list[dict] = []
        for manifest in self._manifests:
            plugin_id = manifest["id"]
            if not self._config.plugin_enabled(plugin_id):
                continue
            effective.append(manifest)
            for inst in self._config.plugin_instances(plugin_id):
                synthetic = dict(manifest)
                synthetic["id"] = inst["id"]
                synthetic["_type"] = plugin_id  # 实际执行的插件类型
                if inst["name"]:
                    for lang in ("zh-Hans", "en"):
                        base = localized(manifest, "name", lang)
                        synthetic[f"name@{lang}"] = f"{base} · {inst['name']}"
                effective.append(synthetic)
        return effective

    def _rebuild_cards(self) -> None:
        effective = self._effective_manifests()
        keep = {m["id"] for m in effective}
        for card_id in list(self._panel._cards.keys()):
            if card_id not in keep:
                self._panel.remove_card(card_id)
        self._panel.set_manifests(effective)

    def refresh_all(self) -> None:
        if self._pending:
            return  # 上一轮未完成
        language = i18n.language()
        for manifest in self._effective_manifests():
            card_id = manifest["id"]
            plugin_type = manifest.get("_type", card_id)
            params = self._config.plugin_params(card_id) \
                if plugin_type == card_id else self._config.instance_params(card_id)
            self._pending.add(card_id)
            self._pool.refresh(plugin_type, params, language, card_id=card_id)
        if self._pending:
            self._panel.set_refreshing(True)

    def _on_result(self, card_id: str, result: dict) -> None:
        self._pending.discard(card_id)
        self._panel.show_result(card_id, result)
        if not self._pending:
            self._panel.set_refreshing(False)

    # ─── 设置 ───

    def open_settings(self) -> None:
        # 暂存配置：取消时丢弃全部改动（包括添加/删除账号）
        staged = Config(self._config.path)
        staged.data = copy.deepcopy(self._config.data)
        dialog = SettingsDialog(staged, self._manifests, self._panel)
        if dialog.exec():
            self._config.data = staged.data
            self._config.save()
            language = self._config.language or i18n.system_language()
            i18n.set_language(language)
            self._timer.start(self._config.refresh_interval_sec * 1000)
            self._rebuild_cards()
            self.refresh_all()

    def _quit(self) -> None:
        self._tray.hide()
        self._pool.wait_for_done(3000)
        self._qt.quit()

    def run(self) -> int:
        return self._qt.exec()


def main() -> int:
    return UsageBoardApp().run()


if __name__ == "__main__":
    sys.exit(main())
