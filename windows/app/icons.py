"""手绘工具栏图标：笔画风格对齐 SF Symbols（arrow.clockwise / gear / power）。

Windows 上 emoji/符号字体回退不稳定（"⚙" 会渲染成异形），
改为 QPainter 绘制，跨平台结果确定。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

_NORMAL = QColor("#3c3c43")     # 接近 NSColor.secondaryLabelColor
_DISABLED = QColor("#c7c7cc")

_RENDER_SIZE = 48               # 高分辨率渲染，缩放显示保证清晰


def _draw(kind: str, color: QColor, size: int = _RENDER_SIZE) -> QPixmap:
    s = size / 16.0  # 以 16pt 为基准缩放
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.35 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    c = size / 2.0

    if kind == "refresh":  # arrow.clockwise：300° 圆弧（缺口在右上）+ 顶部箭头
        r = 5.2 * s
        painter.drawArc(QRectF(c - r, c - r, 2 * r, 2 * r), 90 * 16, 300 * 16)
        tip = QPointF(c, c - r)
        painter.drawLine(tip, QPointF(tip.x() - 2.9 * s, tip.y() - 2.2 * s))
        painter.drawLine(tip, QPointF(tip.x() - 2.9 * s, tip.y() + 2.2 * s))
    elif kind == "power":  # power：顶部缺口的圆弧 + 竖线
        r = 5.2 * s
        painter.drawArc(QRectF(c - r, c - r + 1.1 * s, 2 * r, 2 * r),
                        (90 + 42) * 16, (360 - 84) * 16)
        painter.drawLine(QPointF(c, 1.4 * s), QPointF(c, 7.4 * s))
    elif kind == "gear":  # gear：外圈 + 8 齿 + 内孔
        r_out = 4.4 * s
        painter.drawEllipse(QPointF(c, c), r_out, r_out)
        for i in range(8):
            angle = math.radians(i * 45)
            inner = QPointF(c + math.cos(angle) * (r_out + 0.3 * s),
                            c + math.sin(angle) * (r_out + 0.3 * s))
            outer = QPointF(c + math.cos(angle) * (r_out + 2.1 * s),
                            c + math.sin(angle) * (r_out + 2.1 * s))
            painter.drawLine(inner, outer)
        painter.drawEllipse(QPointF(c, c), 1.6 * s, 1.6 * s)
    elif kind == "chevron-down":  # chevron.down：收起弹层
        left = QPointF(c - 4.6 * s, c - 1.6 * s)
        mid = QPointF(c, c + 3.0 * s)
        right = QPointF(c + 4.6 * s, c - 1.6 * s)
        painter.drawLine(left, mid)
        painter.drawLine(mid, right)
    else:
        raise ValueError(f"unknown icon kind: {kind}")

    painter.end()
    return pixmap


def icon(kind: str) -> QIcon:
    result = QIcon()
    result.addPixmap(_draw(kind, _NORMAL), QIcon.Mode.Normal)
    result.addPixmap(_draw(kind, _DISABLED), QIcon.Mode.Disabled)
    return result
