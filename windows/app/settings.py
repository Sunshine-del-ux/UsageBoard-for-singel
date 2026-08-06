"""设置对话框：由插件清单动态生成参数表单。"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QVBoxLayout, QWidget,
)

from . import i18n
from .config import Config
from .plugins import localized


class SettingsDialog(QDialog):
    def __init__(self, config: Config, manifests: list[dict[str, Any]],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._config = config
        self._manifests = manifests
        self._fields: dict[str, dict[str, Any]] = {}  # plugin_id -> {param_name: widget}
        self._enabled_boxes: dict[str, QCheckBox] = {}

        self.setWindowTitle(i18n.tr("settings"))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        # ─── 通用设置 ───
        general = QGroupBox(i18n.tr("settings_general"))
        form = QFormLayout(general)

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
        layout.addWidget(general)

        # ─── 插件设置 ───
        for manifest in manifests:
            layout.addWidget(self._build_plugin_group(manifest))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_plugin_group(self, manifest: dict[str, Any]) -> QGroupBox:
        plugin_id = manifest["id"]
        language = i18n.language()
        name = localized(manifest, "name", language)

        box = QGroupBox()
        outer = QVBoxLayout(box)
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{name}</b>"))
        header.addStretch(1)
        enabled = QCheckBox(i18n.tr("enabled"))
        enabled.setChecked(self._config.plugin_enabled(plugin_id))
        self._enabled_boxes[plugin_id] = enabled
        header.addWidget(enabled)
        outer.addLayout(header)

        description = localized(manifest, "description", language)
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #888; font-size: 11px;")
            outer.addWidget(desc_label)

        form = QFormLayout()
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
        outer.addLayout(form)
        self._fields[plugin_id] = fields
        return box

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
