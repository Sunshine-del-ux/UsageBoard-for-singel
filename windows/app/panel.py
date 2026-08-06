"""无边框弹出面板：托盘左键切换显示，失焦自动隐藏。

布局对齐 Mac 版 OverviewView：圆角弹层 + 顶栏（图标 + 标题 + borderless
图标按钮）+ 分隔线 + 卡片滚动区。
"""
from __future__ import annotations

import sys
import time
from typing import Any

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from . import i18n, icons, theme
from .cards import PluginCard

PANEL_WIDTH = 380       # Mac 弹层宽 380
PANEL_MAX_HEIGHT = 560


class Panel(QWidget):
    refresh_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # 顶层窗口的样式表背景必须带 WA_StyledBackground，否则 Windows 上不绘制
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(PANEL_WIDTH)
        self.setObjectName("panelRoot")
        self.setStyleSheet(
            f"#panelRoot {{ background: {theme.CANVAS};"
            f" border: 1px solid {theme.CARD_BORDER}; border-radius: 12px; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ─── 顶栏：应用图标 + 标题 + 刷新/设置/退出 ───
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 12, 8)
        header_layout.setSpacing(4)

        icon_label = QLabel()
        icon_label.setPixmap(
            QPixmap(str(theme.app_icon_path())).scaled(
                22, 22,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        icon_label.setFixedSize(22, 22)
        header_layout.addWidget(icon_label)
        header_layout.addSpacing(6)

        title = QLabel("UsageBoard")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self._refresh_button = self._make_tool_button("refresh", i18n.tr("refresh_now"))
        self._refresh_button.clicked.connect(self.refresh_requested)
        header_layout.addWidget(self._refresh_button)

        self._settings_button = self._make_tool_button("gear", i18n.tr("settings"))
        self._settings_button.clicked.connect(self.settings_requested)
        header_layout.addWidget(self._settings_button)

        quit_button = self._make_tool_button("power", i18n.tr("quit"))
        quit_button.clicked.connect(self.quit_requested)
        header_layout.addWidget(quit_button)
        root.addWidget(header)

        root.addWidget(theme.divider())

        # ─── 卡片滚动区 ───
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._container)
        self._cards_layout.setContentsMargins(12, 8, 12, 12)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch(1)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll)

        self._cards: dict[str, PluginCard] = {}
        self._hidden_at = 0.0  # 最近一次失焦自动隐藏的时间戳

    @staticmethod
    def _make_tool_button(icon_kind: str, tooltip: str) -> QPushButton:
        from PySide6.QtCore import QSize
        button = QPushButton()
        button.setIcon(icons.icon(icon_kind))
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(26, 26)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(theme.TOOL_BUTTON_STYLE)
        return button

    def set_manifests(self, manifests: list[dict[str, Any]]) -> None:
        for manifest in manifests:
            plugin_id = manifest["id"]
            if plugin_id in self._cards:
                continue
            card = PluginCard(manifest)
            self._cards[plugin_id] = card
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
        self._refit()

    def remove_card(self, plugin_id: str) -> None:
        card = self._cards.pop(plugin_id, None)
        if card is not None:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._refit()

    def show_result(self, plugin_id: str, result: dict[str, Any]) -> None:
        card = self._cards.get(plugin_id)
        if card is not None:
            card.show_result(result)
            self._refit()

    def set_refreshing(self, refreshing: bool) -> None:
        self._refresh_button.setEnabled(not refreshing)

    # ─── 显示/定位 ───

    def toggle_near(self, anchor_bottom_right: bool = True) -> None:
        if self.isVisible():
            self.hide()
            return
        # 点托盘图标会先让面板失焦自动隐藏，随后 activated 信号才到；
        # 若刚刚因此隐藏，说明用户意图是收起而非重新打开
        if time.monotonic() - self._hidden_at < 0.35:
            return
        self.show_near()

    def show_near(self) -> None:
        self._dismiss_tray_flyout()
        # 等 ESC 收掉系统托盘弹窗后再显示，避免被遮挡
        QTimer.singleShot(80, self._show_and_position)

    def _show_and_position(self) -> None:
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

    @staticmethod
    def _dismiss_tray_flyout() -> None:
        """Windows：发送 ESC 收起托盘溢出弹窗/菜单，避免遮挡面板。"""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.keybd_event(0x1B, 0, 0, 0)          # ESC 按下
            user32.keybd_event(0x1B, 0, 0x0002, 0)     # ESC 抬起（KEYEVENTF_KEYUP）
        except Exception:
            pass

    def _fit_height(self) -> None:
        self._container.adjustSize()
        content = self._container.sizeHint().height() + 48  # 顶栏 + 分隔线
        self.setFixedHeight(min(max(content, 160), PANEL_MAX_HEIGHT))

    def _refit(self) -> None:
        """内容变化后随内容自适应高度（仅在弹层可见时）。

        立即拟合一次，再延迟补一次以覆盖自动换行文本的稳定布局。
        """
        if self.isVisible():
            self._fit_height()
            QTimer.singleShot(0, self._fit_height)

    def hideEvent(self, event: QEvent) -> None:
        self._hidden_at = time.monotonic()
        super().hideEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowDeactivate:
            self.hide()
        super().changeEvent(event)
