"""设置对话框：由插件清单动态生成参数表单，支持同类型插件多账号。

风格对齐 macOS 系统设置：粗体分组标题 + 白色圆角卡片表单，
而非 Qt 默认的刻蚀边框 QGroupBox。

对话框编辑的是暂存配置（内存副本）：保存时由调用方落盘，
取消则丢弃全部改动（包括添加/删除账号）。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
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


def _flat_button(text: str, color: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        f"QPushButton {{ color: {color}; border: none; background: transparent;"
        f" padding: 2px 4px; font-size: 12px; }}"
        f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
    )
    return button


class SettingsDialog(QDialog):
    def __init__(self, config: Config, manifests: list[dict[str, Any]],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._config = config
        self._manifests = manifests
        self._fields: dict[str, dict[str, Any]] = {}          # plugin_id -> {param: widget}
        self._instance_fields: dict[str, dict[str, Any]] = {}  # instance_id -> {param: widget}
        self._enabled_boxes: dict[str, QCheckBox] = {}
        self._name_edits: dict[str, QLineEdit] = {}            # instance_id -> 备注名输入框

        self.setWindowTitle(i18n.tr("settings"))
        self.setMinimumWidth(460)
        self.setMaximumHeight(680)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 10, 0, 0)
        root.setSpacing(10)

        # 内容区可滚动：多账号时分组变多，底部保存按钮固定可见
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(18, 6, 18, 4)
        self._content_layout.setSpacing(14)
        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll, 1)

        button_row = QWidget()
        button_layout = QVBoxLayout(button_row)
        button_layout.setContentsMargins(18, 0, 18, 12)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText(i18n.tr("save"))
        save_button.setDefault(True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(i18n.tr("cancel"))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        root.addWidget(button_row)

        self._rebuild()

    # ─── 界面构建 ────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        """按当前暂存配置重建全部分组（添加/删除账号后调用）。"""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # 先隐藏再延迟删除：可见状态下 deleteLater 未处理前旧控件仍会绘制
                widget.hide()
                widget.deleteLater()
        self._fields.clear()
        self._instance_fields.clear()
        self._enabled_boxes.clear()
        self._name_edits.clear()

        # ─── 通用设置 ───
        general, general_body = _section(i18n.tr("settings_general"))
        form = QFormLayout()
        form.setSpacing(8)

        self._language_combo = QComboBox()
        self._language_combo.addItem(i18n.tr("language_auto"), None)
        self._language_combo.addItem("简体中文", "zh-Hans")
        self._language_combo.addItem("English", "en")
        index = self._language_combo.findData(self._config.language)
        self._language_combo.setCurrentIndex(max(0, index))
        form.addRow(i18n.tr("language"), self._language_combo)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(30, 86400)
        self._interval_spin.setValue(self._config.refresh_interval_sec)
        form.addRow(i18n.tr("refresh_interval"), self._interval_spin)
        general_body.addLayout(form)
        self._content_layout.addWidget(general)

        # ─── 插件设置 ───
        for manifest in self._manifests:
            self._content_layout.addWidget(self._build_plugin_section(manifest))

        self._content_layout.addStretch(1)
        self.adjustSize()

    def _add_param_rows(self, form: QFormLayout, manifest: dict[str, Any],
                        saved: dict[str, str], fields: dict[str, Any]) -> None:
        language = i18n.language()
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

        # 默认账号（沿用既有 plugin_id 配置，保持兼容）
        form = QFormLayout()
        form.setSpacing(8)
        fields: dict[str, Any] = {}
        self._add_param_rows(form, manifest, self._config.plugin_params(plugin_id), fields)
        self._fields[plugin_id] = fields
        body.addLayout(form)

        # 额外账号实例
        instances = self._config.plugin_instances(plugin_id)
        for index, inst in enumerate(instances):
            body.addWidget(theme.divider())
            inst_form = QFormLayout()
            inst_form.setSpacing(8)

            name_row = QHBoxLayout()
            name_edit = QLineEdit(inst["name"])
            name_edit.setPlaceholderText(i18n.tr("account_default", n=index + 2))
            self._name_edits[inst["id"]] = name_edit
            remove = _flat_button(i18n.tr("remove_account"), theme.DANGER)
            remove.clicked.connect(
                lambda checked=False, iid=inst["id"]: self._remove_instance(iid))
            name_row.addWidget(name_edit, 1)
            name_row.addWidget(remove)
            inst_form.addRow(i18n.tr("account_name"), name_row)

            inst_fields: dict[str, Any] = {}
            self._add_param_rows(inst_form, manifest, inst["params"], inst_fields)
            self._instance_fields[inst["id"]] = inst_fields
            body.addLayout(inst_form)

        # 添加同类型账号
        if instances:
            body.addWidget(theme.divider())
        add = _flat_button(f"＋ {i18n.tr('add_account')}", theme.ACCENT)
        add.clicked.connect(
            lambda checked=False, pid=plugin_id: self._add_instance(pid))
        body.addWidget(add)

        outer.addWidget(card)
        return container

    # ─── 账号增删 ────────────────────────────────────────────────────────────

    def _add_instance(self, plugin_id: str) -> None:
        self._harvest()  # 先收割表单，避免重建丢失未保存输入
        count = len(self._config.plugin_instances(plugin_id))
        self._config.add_instance(
            plugin_id, i18n.tr("account_default", n=count + 2))
        self._rebuild()

    def _remove_instance(self, instance_id: str) -> None:
        self._harvest()
        self._config.remove_instance(instance_id)
        self._rebuild()

    # ─── 收割与保存 ──────────────────────────────────────────────────────────

    def _harvest(self) -> None:
        """把当前表单值写回暂存配置（不写磁盘）。"""
        self._config.language = self._language_combo.currentData()
        self._config.refresh_interval_sec = self._interval_spin.value()
        for plugin_id, box in self._enabled_boxes.items():
            self._config.set_plugin_enabled(plugin_id, box.isChecked())

        def collect(fields: dict[str, Any]) -> dict[str, str]:
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
            return params

        for plugin_id, fields in self._fields.items():
            self._config.set_plugin_params(plugin_id, collect(fields))
        for instance_id, fields in self._instance_fields.items():
            self._config.set_instance_params(instance_id, collect(fields))
        for instance_id, edit in self._name_edits.items():
            self._config.rename_instance(instance_id, edit.text().strip())

    def _save(self) -> None:
        self._harvest()
        self.accept()
