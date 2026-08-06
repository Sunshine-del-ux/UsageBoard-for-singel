"""设置对话框：由插件清单动态生成参数表单。

风格对齐 macOS 系统设置：粗体分组标题 + 白色圆角卡片表单，
而非 Qt 默认的刻蚀边框 QGroupBox。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QSpinBox, QVBoxLayout, QWidget,
)

from . import i18n, theme
from .config import Config
from .plugins import localized


def _section(title: str) -> tuple[QWidget, QVBoxLayout]:
    """一个设置分组：返回（容器， 白色圆角卡片的内容布局）。"""
    container = QWidget()
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(6)

    label = QLabel(title)
    label.setStyleSheet("font-size: 13px; font-weight: 600;")
    outer.addWidget(label)

    card = QFrame()
    card.setObjectName("settingsCard")
    card.setStyleSheet(
        f"#settingsCard {{ background: {theme.CARD};"
        f" border: 1px solid {theme.CARD_BORDER}; border-radius: 10px; }}"
    )
    body = QVBoxLayout(card)
    body.setContentsMargins(14, 10, 14, 10)
    body.setSpacing(8)
    outer.addWidget(card)
    return container, body


class SettingsDialog(QDialog):
    def __init__(self, config: Config, manifests: list[dict[str, Any]],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._config = config
        self._manifests = manifests
        self._fields: dict[str, dict[str, Any]] = {}  # plugin_id -> {param_name: widget}
        self._enabled_boxes: dict[str, QCheckBox] = {}

        self.setWindowTitle(i18n.tr("settings"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(14)

        # ─── 通用设置 ───
        general, general_body = _section(i18n.tr("settings_general"))
        form = QFormLayout()
        form.setSpacing(8)

        self._language_combo = QComboBox()
        self._language_combo.addItem(i18n.tr("language_auto"), None)
        self._language_combo.addItem("简体中文", "zh-Hans")
        self._language_combo.addItem("English", "en")
        current = config.language
        index = self._language_combo.findData(current)
        self._language_combo.setCurrentIndex(max(0, index))
        form.addRow(i18n.tr("language"), self._language_combo)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(30, 86400)
        self._interval_spin.setValue(config.refresh_interval_sec)
        form.addRow(i18n.tr("refresh_interval"), self._interval_spin)
        general_body.addLayout(form)
        layout.addWidget(general)

        # ─── 插件设置 ───
        for manifest in manifests:
            layout.addWidget(self._build_plugin_section(manifest))

        layout.addSpacing(2)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText(i18n.tr("save"))
        save_button.setDefault(True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(i18n.tr("cancel"))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_plugin_section(self, manifest: dict[str, Any]) -> QWidget:
        plugin_id = manifest["id"]
        language = i18n.language()
        name = localized(manifest, "name", language)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # 标题行：插件名 + 启用开关（对齐 Mac 设置页的 toggle 位置）
        header = QHBoxLayout()
        title = QLabel(name)
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        enabled = QCheckBox(i18n.tr("enabled"))
        enabled.setChecked(self._config.plugin_enabled(plugin_id))
        self._enabled_boxes[plugin_id] = enabled
        header.addWidget(enabled)
        outer.addLayout(header)

        card = QFrame()
        card.setObjectName("settingsCard")
        card.setStyleSheet(
            f"#settingsCard {{ background: {theme.CARD};"
            f" border: 1px solid {theme.CARD_BORDER}; border-radius: 10px; }}"
        )
        body = QVBoxLayout(card)
        body.setContentsMargins(14, 10, 14, 10)
        body.setSpacing(8)

        description = localized(manifest, "description", language)
        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
            )
            body.addWidget(desc_label)

        form = QFormLayout()
        form.setSpacing(8)
        saved = self._config.plugin_params(plugin_id)
        fields: dict[str, Any] = {}
        for param in manifest.get("parameters", []):
            pname = param.get("name")
            if not pname:
                continue
            label = localized(param, "label", language)
            ptype = param.get("type", "string")
            value = saved.get(pname, str(param.get("defaultValue", "")))

            if ptype == "choice":
                widget: Any = QComboBox()
                for option in param.get("options", []):
                    widget.addItem(localized(option, "label", language), option.get("value"))
                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif ptype == "secret":
                widget = QLineEdit(value)
                widget.setEchoMode(QLineEdit.EchoMode.Password)
                widget.setPlaceholderText(str(param.get("placeholder", "")))
            else:  # integer / string
                widget = QLineEdit(value)
                widget.setPlaceholderText(str(param.get("placeholder", "")))
            fields[pname] = widget
            form.addRow(label, widget)
        body.addLayout(form)
        outer.addWidget(card)
        self._fields[plugin_id] = fields
        return container

    def _save(self) -> None:
        self._config.language = self._language_combo.currentData()
        self._config.refresh_interval_sec = self._interval_spin.value()
        for plugin_id, fields in self._fields.items():
            self._config.set_plugin_enabled(plugin_id, self._enabled_boxes[plugin_id].isChecked())
            params: dict[str, str] = {}
            for pname, widget in fields.items():
                if isinstance(widget, QComboBox):
                    value = widget.currentData()
                    if value is not None:
                        params[pname] = str(value)
                else:
                    text = widget.text().strip()
                    if text:
                        params[pname] = text
            self._config.set_plugin_params(plugin_id, params)
        self._config.save()
        self.accept()
