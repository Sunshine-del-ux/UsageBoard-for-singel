"""单面板卡片：每个插件一张卡，卡内逐条展示用量项。"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from . import i18n
from .plugins import localized

COLOR_HEX = {
    "blue": "#3B82F6",
    "yellow": "#EAB308",
    "orange": "#F97316",
    "red": "#EF4444",
}


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _format_reset(reset_at: Any) -> str:
    """ISO 时间 → 本地简短格式；解析失败则原样返回。"""
    if not reset_at:
        return ""
    text = str(reset_at)
    try:
        from datetime import datetime
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return text


class ItemRow(QWidget):
    """一条用量：名称 + 进度条/百分比 + 数值 + 重置时间。"""

    def __init__(self, item: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        color = COLOR_HEX.get(str(item.get("color")), COLOR_HEX["blue"])
        name = str(item.get("name", ""))
        used = item.get("used")
        limit = item.get("limit")
        style = item.get("displayStyle", "ratio")

        top = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: 600;")
        top.addWidget(name_label)
        top.addStretch(1)

        used_text = _format_number(used)
        limit_text = _format_number(limit) if limit not in (None, "", 0) else None
        if limit_text:
            value_text = i18n.tr("usage_of", used=used_text, limit=limit_text)
        else:
            value_text = i18n.tr("no_limit", used=used_text)
        value_label = QLabel(value_text)
        value_label.setStyleSheet("color: #888;")
        top.addWidget(value_label)
        layout.addLayout(top)

        try:
            pct = float(used) / float(limit) * 100 if limit else 0.0
        except (TypeError, ValueError, ZeroDivisionError):
            pct = 0.0
        pct = max(0.0, min(100.0, pct))

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(round(pct)))
        bar.setTextVisible(style == "percent")
        if style == "percent":
            bar.setFormat(f"{pct:.1f}%")
            bar.setFixedHeight(14)
        else:
            bar.setFixedHeight(8)
        bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 4px; background: #e6e6e6; }"
            f"QProgressBar::chunk {{ border-radius: 4px; background: {color}; }}"
        )
        layout.addWidget(bar)

        reset_text = _format_reset(item.get("resetAt"))
        if reset_text:
            reset_label = QLabel(i18n.tr("reset_at", time=reset_text))
            reset_label.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(reset_label)


class PluginCard(QFrame):
    """一张插件卡：标题行（名称 + 徽标）+ 若干 ItemRow，或错误提示。"""

    def __init__(self, manifest: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("pluginCard")
        self.setStyleSheet(
            "#pluginCard { background: #ffffff; border: 1px solid #e3e3e3; border-radius: 10px; }"
            "QLabel { color: #222; background: transparent; }"
        )
        self._manifest = manifest
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 12)
        self._layout.setSpacing(6)
        self._show_loading()

    def _clear(self) -> None:
        while self._layout.count():
            child = self._layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
            elif child.layout() is not None:
                while child.layout().count():
                    sub = child.layout().takeAt(0)
                    if sub.widget() is not None:
                        sub.widget().deleteLater()

    def _header(self, badge: str | None, badge_color: str | None) -> None:
        row = QHBoxLayout()
        title = QLabel(localized(self._manifest, "name", i18n.language()))
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        row.addWidget(title)
        if badge:
            chip = QLabel(badge)
            color = COLOR_HEX.get(str(badge_color or ""), "#6b7280")
            chip.setStyleSheet(
                f"background: {color}; color: white; border-radius: 8px;"
                "padding: 1px 8px; font-size: 11px; font-weight: 600;"
            )
            row.addWidget(chip)
        row.addStretch(1)
        self._layout.addLayout(row)

    def _show_loading(self) -> None:
        self._clear()
        self._header(None, None)
        label = QLabel(i18n.tr("loading"))
        label.setStyleSheet("color: #888;")
        self._layout.addWidget(label)

    def show_result(self, result: dict[str, Any]) -> None:
        self._clear()
        error = result.get("error")
        if error:
            self._header(None, None)
            label = QLabel(str(error))
            label.setWordWrap(True)
            label.setStyleSheet("color: #EF4444;")
            self._layout.addWidget(label)
            return

        badge = result.get("badge")
        badge_color = result.get("badgeColor")
        self._header(str(badge) if badge else None, str(badge_color) if badge_color else None)

        items = result.get("items") or []
        for item in items:
            self._layout.addWidget(ItemRow(item))
        if not items:
            label = QLabel(i18n.tr("never_updated"))
            label.setStyleSheet("color: #888;")
            self._layout.addWidget(label)
