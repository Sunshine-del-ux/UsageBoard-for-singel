"""系统托盘图标与菜单。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import i18n


class Tray(QObject):
    show_panel_requested = Signal()
    refresh_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon, parent: QObject | None = None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("UsageBoard")

        menu = QMenu()
        self._action_panel = QAction(i18n.tr("show_panel"), menu)
        self._action_panel.triggered.connect(self.show_panel_requested)
        menu.addAction(self._action_panel)

        action_refresh = QAction(i18n.tr("refresh_now"), menu)
        action_refresh.triggered.connect(self.refresh_requested)
        menu.addAction(action_refresh)

        action_settings = QAction(i18n.tr("settings"), menu)
        action_settings.triggered.connect(self.settings_requested)
        menu.addAction(action_settings)

        menu.addSeparator()
        action_quit = QAction(i18n.tr("quit"), menu)
        action_quit.triggered.connect(self.quit_requested)
        menu.addAction(action_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # 左键
            self.show_panel_requested.emit()

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()
