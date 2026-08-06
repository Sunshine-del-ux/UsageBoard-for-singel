"""入口：QApplication + 托盘 + 面板 + 定时刷新。"""
from __future__ import annotations

import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from . import i18n, theme
from .config import Config, config_dir
from .panel import Panel
from .plugins import all_manifests
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

    def _rebuild_cards(self) -> None:
        enabled = [m for m in self._manifests if self._config.plugin_enabled(m["id"])]
        enabled_ids = {m["id"] for m in enabled}
        for plugin_id in list(self._panel._cards.keys()):
            if plugin_id not in enabled_ids:
                self._panel.remove_card(plugin_id)
        self._panel.set_manifests(enabled)

    def refresh_all(self) -> None:
        if self._pending:
            return  # 上一轮未完成
        language = i18n.language()
        for manifest in self._manifests:
            plugin_id = manifest["id"]
            if not self._config.plugin_enabled(plugin_id):
                continue
            self._pending.add(plugin_id)
            params = self._config.plugin_params(plugin_id)
            self._pool.refresh(plugin_id, params, language)
        if self._pending:
            self._panel.set_refreshing(True)

    def _on_result(self, plugin_id: str, result: dict) -> None:
        self._pending.discard(plugin_id)
        self._panel.show_result(plugin_id, result)
        if not self._pending:
            self._panel.set_refreshing(False)

    # ─── 设置 ───

    def open_settings(self) -> None:
        dialog = SettingsDialog(self._config, self._manifests, self._panel)
        if dialog.exec():
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
