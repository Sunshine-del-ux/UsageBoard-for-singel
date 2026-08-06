"""无边框弹出面板：托盘左键切换显示，失焦自动隐藏。"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from . import i18n
from .cards import PluginCard

PANEL_WIDTH = 360
PANEL_MAX_HEIGHT = 560


class Panel(QWidget):
    refresh_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(PANEL_WIDTH)
        self.setStyleSheet("background: #1f1f1f;")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        # ─── 顶部工具行 ───
        toolbar = QHBoxLayout()
        title = QLabel("UsageBoard")
        title.setStyleSheet("color: #eee; font-size: 14px; font-weight: 700;")
        toolbar.addWidget(title)
        toolbar.addStretch(1)

        self._refresh_button = QPushButton("⟳")
        self._refresh_button.setFixedSize(28, 28)
        self._refresh_button.setToolTip(i18n.tr("refresh_now"))
        self._refresh_button.clicked.connect(self.refresh_requested)
        toolbar.addWidget(self._refresh_button)

        self._settings_button = QPushButton("⚙")
        self._settings_button.setFixedSize(28, 28)
        self._settings_button.setToolTip(i18n.tr("settings"))
        self._settings_button.clicked.connect(self.settings_requested)
        toolbar.addWidget(self._settings_button)
        root.addLayout(toolbar)

        # ─── 卡片滚动区 ───
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch(1)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll)

        self._cards: dict[str, PluginCard] = {}

    def set_manifests(self, manifests: list[dict[str, Any]]) -> None:
        for manifest in manifests:
            plugin_id = manifest["id"]
            if plugin_id in self._cards:
                continue
            card = PluginCard(manifest)
            self._cards[plugin_id] = card
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def remove_card(self, plugin_id: str) -> None:
        card = self._cards.pop(plugin_id, None)
        if card is not None:
            self._cards_layout.removeWidget(card)
            card.deleteLater()

    def show_result(self, plugin_id: str, result: dict[str, Any]) -> None:
        card = self._cards.get(plugin_id)
        if card is not None:
            card.show_result(result)

    def set_refreshing(self, refreshing: bool) -> None:
        self._refresh_button.setEnabled(not refreshing)
        self._refresh_button.setText("…" if refreshing else "⟳")

    # ─── 显示/定位 ───

    def toggle_near(self, anchor_bottom_right: bool = True) -> None:
        if self.isVisible():
            self.hide()
            return
        self.show_near()

    def show_near(self) -> None:
        self._fit_height()
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            x = available.right() - self.width() - 12
            y = available.bottom() - self.height() - 12
            self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _fit_height(self) -> None:
        self._container.adjustSize()
        content = self._container.sizeHint().height() + 60
        self.setFixedHeight(min(max(content, 160), PANEL_MAX_HEIGHT))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowDeactivate:
            self.hide()
        super().changeEvent(event)
