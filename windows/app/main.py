"""入口：QApplication + 托盘 + 面板 + 定时刷新。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from . import i18n
from .config import Config
from .panel import Panel
from .plugins import all_manifests
from .settings import SettingsDialog
from .tray import Tray
from .worker import WorkerPool


def _icon_path() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "icon.png"
    return Path(__file__).resolve().parents[2] / "Resources" / "icon.png"


def _apply_light_theme(app: QApplication) -> None:
    """固定 Fusion 风格 + 浅色调色板。

    面板/卡片本身是浅色硬编码样式；若跟随系统主题（尤其 Windows 11 暗色
    原生样式），对话框会出现渲染不一致。Fusion 跨平台渲染结果确定。
    """
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#f5f5f5",
        QPalette.ColorRole.WindowText: "#222222",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f5f5f5",
        QPalette.ColorRole.ToolTipBase: "#ffffff",
        QPalette.ColorRole.ToolTipText: "#222222",
        QPalette.ColorRole.Text: "#222222",
        QPalette.ColorRole.Button: "#efefef",
        QPalette.ColorRole.ButtonText: "#222222",
        QPalette.ColorRole.BrightText: "#ef4444",
        QPalette.ColorRole.Highlight: "#3b82f6",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: "#999999",
        QPalette.ColorRole.Link: "#3b82f6",
        QPalette.ColorRole.Light: "#ffffff",
        QPalette.ColorRole.Midlight: "#e8e8e8",
        QPalette.ColorRole.Mid: "#cfcfcf",
        QPalette.ColorRole.Dark: "#a5a5a5",
        QPalette.ColorRole.Shadow: "#bdbdbd",
    }
    for role, hex_color in colors.items():
        palette.setColor(role, QColor(hex_color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.WindowText, QPalette.ColorRole.PlaceholderText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#aaaaaa"))
    app.setPalette(palette)


class UsageBoardApp:
    def __init__(self):
        self._qt = QApplication(sys.argv)
        self._qt.setQuitOnLastWindowClosed(False)
        self._qt.setApplicationName("UsageBoard")
        _apply_light_theme(self._qt)

        icon = QIcon(str(_icon_path()))
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
