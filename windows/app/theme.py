"""macOS 风格浅色主题：调色板 + 全局控件样式表 + 设计常量。

对齐 Mac 版 SwiftUI 实现（UBDesignTokens / PluginGroupView）：
- 画布 #ececec（NSColor.windowBackgroundColor），卡片纯白、10px 圆角、极浅描边；
- 输入控件 6px 圆角细边框，主按钮使用强调蓝；
- Fusion 风格保证 Windows/macOS 渲染一致（本文件在 Mac 上 offscreen 验证）。
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

# ─── 颜色常量（与卡片/面板硬编码样式共用）───
CANVAS = "#ececec"          # macOS windowBackgroundColor（浅色）
CARD = "#ffffff"            # textBackgroundColor
CARD_BORDER = "#e3e3e6"     # separatorColor 70% 不透明度近似
SEPARATOR = "#e8e8eb"
TEXT_PRIMARY = "#1d1d1f"    # 接近 NSColor.labelColor
TEXT_SECONDARY = "#6e6e73"  # secondaryLabelColor
TEXT_TERTIARY = "#8e8e93"   # tertiaryLabelColor
ACCENT = "#3b82f6"
ACCENT_PRESSED = "#2f6fe0"
INPUT_BORDER = "#d5d5da"
DANGER = "#ef4444"

COLOR_HEX = {
    "blue": "#3B82F6",
    "yellow": "#EAB308",
    "orange": "#F97316",
    "red": "#EF4444",
}

APP_STYLESHEET = f"""
/* ─── 输入控件：macOS 风格 6px 圆角细边框 ─── */
QLineEdit, QComboBox, QSpinBox {{
    background: #ffffff;
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 18px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: #f5f5f7;
    color: {TEXT_TERTIARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: #ffffff;
    border: 1px solid {INPUT_BORDER};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    border: none;
    width: 18px;
}}

/* ─── 按钮：白底圆角，默认按钮用强调蓝 ─── */
QPushButton {{
    background: #ffffff;
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    padding: 5px 16px;
}}
QPushButton:hover {{
    background: #f5f5f7;
}}
QPushButton:pressed {{
    background: #e8e8eb;
}}
QPushButton:default {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: #ffffff;
}}
QPushButton:default:hover {{
    background: #4a8cf8;
}}
QPushButton:default:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton:disabled {{
    color: {TEXT_TERTIARY};
    background: #f5f5f7;
}}

/* ─── 其它控件 ─── */
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QCheckBox {{
    spacing: 6px;
}}
QToolTip {{
    background: #ffffff;
    border: 1px solid {INPUT_BORDER};
    color: {TEXT_PRIMARY};
    padding: 4px 6px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #c7c7cc;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #aeaeb2;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #c7c7cc;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""

# 面板顶栏图标按钮：borderless，悬停出浅灰圆角底
TOOL_BUTTON_STYLE = f"""
QPushButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 0px;
}}
QPushButton:hover {{
    background: rgba(0, 0, 0, 0.06);
}}
QPushButton:pressed {{
    background: rgba(0, 0, 0, 0.11);
}}
"""


def apply_palette(app) -> None:
    """固定 Fusion 风格 + macOS 浅色调色板（跨平台渲染确定）。"""
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: CANVAS,
        QPalette.ColorRole.WindowText: TEXT_PRIMARY,
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f5f5f7",
        QPalette.ColorRole.ToolTipBase: "#ffffff",
        QPalette.ColorRole.ToolTipText: TEXT_PRIMARY,
        QPalette.ColorRole.Text: TEXT_PRIMARY,
        QPalette.ColorRole.Button: "#ffffff",
        QPalette.ColorRole.ButtonText: TEXT_PRIMARY,
        QPalette.ColorRole.BrightText: DANGER,
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: TEXT_TERTIARY,
        QPalette.ColorRole.Link: ACCENT,
        QPalette.ColorRole.Light: "#ffffff",
        QPalette.ColorRole.Midlight: "#e8e8eb",
        QPalette.ColorRole.Mid: "#cfcfd4",
        QPalette.ColorRole.Dark: "#a5a5aa",
        QPalette.ColorRole.Shadow: "#bdbdc2",
    }
    for role, hex_color in colors.items():
        palette.setColor(role, QColor(hex_color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.WindowText, QPalette.ColorRole.PlaceholderText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#aeaeb2"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLESHEET)


def bar_stylesheet(color: str, text_color: str) -> str:
    """macOS 进度条：轨道为主色 16% 透明度的浅色，数值文字画在条内居中。"""
    track = with_alpha(color, 41)  # 0.16 * 255 ≈ 41
    return (
        f"QProgressBar {{ border: none; border-radius: 5px; background: {track};"
        f" color: {text_color}; text-align: center;"
        " font-size: 11px; font-weight: 600; }"
        f"QProgressBar::chunk {{ border-radius: 5px; background: {color}; }}"
    )


def divider():
    """1px 细分隔线（macOS separatorColor）。"""
    from PySide6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {SEPARATOR}; border: none;")
    return line


def app_icon_path():
    """应用图标路径（兼容 PyInstaller 打包目录）。"""
    import sys
    from pathlib import Path
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "icon.png"
    return Path(__file__).resolve().parents[2] / "Resources" / "icon.png"


def with_alpha(hex_color: str, alpha: int) -> str:
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color.name(QColor.NameFormat.HexArgb)
