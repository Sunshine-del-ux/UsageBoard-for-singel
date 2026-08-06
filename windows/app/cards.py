"""单面板卡片：布局对齐 Mac 版 PluginGroupView / UsageItemRow。

每张卡 = 标题行（名称 + 套餐徽标 + 错误胶囊）+ 分隔线 + 若干用量行；
每行 = 名称（灰）| 进度条（数值文字在条内）| 重置时间（浅灰右对齐）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from . import i18n, theme
from .plugins import localized

COLOR_HEX = theme.COLOR_HEX


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _format_reset(reset_at: Any) -> str:
    """对齐 Mac 版 UsageItem.resetText：今天/明天 HH:MM，否则带日期；过期显示 --。"""
    if not reset_at:
        return "--"
    try:
        parsed = datetime.fromisoformat(
            str(reset_at).replace("Z", "+00:00")
        ).astimezone()
    except ValueError:
        return str(reset_at)
    now = datetime.now().astimezone()
    if parsed <= now:
        return "--"
    time_text = parsed.strftime("%H:%M")
    if parsed.date() == now.date():
        return i18n.tr("reset_today", time=time_text)
    if parsed.date() == (now + timedelta(days=1)).date():
        return i18n.tr("reset_tomorrow", time=time_text)
    if i18n.language() == "en":
        return parsed.strftime("%m/%d %H:%M")
    return f"{parsed.month}月{parsed.day}日 {time_text}"


class ItemRow(QWidget):
    """一条用量：名称 + 进度条（数值在条内）+ 重置时间，单行排布。"""

    def __init__(self, item: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        color = COLOR_HEX.get(str(item.get("color")), COLOR_HEX["blue"])
        used = item.get("used")
        limit = item.get("limit")
        style = item.get("displayStyle", "ratio")

        name_label = QLabel(str(item.get("name", "")))
        name_label.setFixedWidth(80)
        name_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(name_label)

        try:
            ratio = max(0.0, min(1.0, float(used) / float(limit))) if limit else 0.0
        except (TypeError, ValueError, ZeroDivisionError):
            ratio = 0.0

        if style == "percent":
            bar_text = f"{round(ratio * 100)}%"
        elif limit:
            bar_text = f"{_format_number(used)} / {_format_number(limit)}"
        else:
            bar_text = i18n.tr("no_limit", used=_format_number(used))

        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(int(round(ratio * 1000)))
        bar.setFixedHeight(18)
        bar.setFormat(bar_text)
        # Mac 版占比 ≥55% 时条内文字反白
        fg = "#ffffff" if ratio >= 0.55 else theme.TEXT_PRIMARY
        bar.setStyleSheet(theme.bar_stylesheet(color, fg))
        layout.addWidget(bar, 1)

        reset_label = QLabel(_format_reset(item.get("resetAt")))
        reset_label.setFixedWidth(90)
        reset_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        reset_label.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; font-size: 11px;")
        layout.addWidget(reset_label)


class PluginCard(QFrame):
    """一张插件卡：白底 10px 圆角 + 细描边（对齐 Mac 卡片样式）。"""

    def __init__(self, manifest: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("pluginCard")
        self.setStyleSheet(
            f"#pluginCard {{ background: {theme.CARD};"
            f" border: 1px solid {theme.CARD_BORDER}; border-radius: 10px; }}"
        )
        self._manifest = manifest
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(8)
        self._show_loading()

    def _clear(self) -> None:
        def discard(widget: QWidget) -> None:
            # 先隐藏再延迟删除：可见状态下 deleteLater 未处理前旧控件仍会绘制
            widget.hide()
            widget.deleteLater()

        while self._layout.count():
            child = self._layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                discard(widget)
            elif child.layout() is not None:
                while child.layout().count():
                    sub = child.layout().takeAt(0)
                    if sub.widget() is not None:
                        discard(sub.widget())

    def _header(self, badge: str | None, badge_color: str | None,
                failed: bool = False) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        title = QLabel(localized(self._manifest, "name", i18n.language()))
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        row.addWidget(title)
        if badge:
            row.addWidget(self._badge_chip(badge, badge_color))
        if failed:
            chip = QLabel(i18n.tr("error_badge"))
            chip.setStyleSheet(
                f"background: {theme.with_alpha(theme.DANGER, 26)};"
                f" color: {theme.DANGER}; border-radius: 8px;"
                " padding: 1px 6px; font-size: 10px; font-weight: 500;"
            )
            row.addWidget(chip)
        row.addStretch(1)
        self._layout.addLayout(row)

    @staticmethod
    def _badge_chip(badge: str, badge_color: str | None) -> QLabel:
        """套餐徽标：对齐 Mac PlanTag —— 着色文字 + 同色 18% 透明底。"""
        color = COLOR_HEX.get(str(badge_color or "").lower(), "#6b7280")
        chip = QLabel(badge.upper())
        chip.setStyleSheet(
            f"background: {theme.with_alpha(color, 46)}; color: {color};"
            " border-radius: 4px; padding: 1px 5px;"
            " font-size: 10px; font-weight: 700;"
        )
        return chip

    def _show_loading(self) -> None:
        self._clear()
        self._header(None, None)
        self._layout.addWidget(theme.divider())
        label = QLabel(i18n.tr("loading"))
        label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        self._layout.addWidget(label)

    def show_result(self, result: dict[str, Any]) -> None:
        self._clear()
        error = result.get("error")
        if error:
            self._header(None, None, failed=True)
            self._layout.addWidget(theme.divider())
            label = QLabel(str(error))
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {theme.DANGER}; font-size: 12px;")
            self._layout.addWidget(label)
            return

        badge = result.get("badge")
        badge_color = result.get("badgeColor")
        self._header(str(badge) if badge else None,
                     str(badge_color) if badge_color else None)
        self._layout.addWidget(theme.divider())

        items = result.get("items") or []
        for item in items:
            self._layout.addWidget(ItemRow(item))
        if not items:
            label = QLabel(i18n.tr("never_updated"))
            label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
            self._layout.addWidget(label)
