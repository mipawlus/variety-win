from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...config.schema import AppConfig, SourceConfig
from ...sources.base import ConfigField
from ...sources.registry import SOURCE_REGISTRY


class _SourceGroup(QGroupBox):
    def __init__(self, source_id: str, source_cls, source_config: SourceConfig, parent=None):
        super().__init__(source_cls.display_name, parent)
        self.source_id = source_id
        self.source_cls = source_cls
        self.setCheckable(True)
        self.setChecked(source_config.enabled)

        layout = QFormLayout(self)
        self._field_widgets: dict[str, tuple[ConfigField, QWidget]] = {}

        for field in source_cls.config_fields():
            value = source_config.options.get(field.key, field.default)
            widget = self._build_widget(field, value)
            self._field_widgets[field.key] = (field, widget)
            layout.addRow(field.label, widget)

    def _build_widget(self, field: ConfigField, value: Any) -> QWidget:
        if field.type == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            return widget

        if field.type == "choice":
            widget = QComboBox()
            widget.addItems(field.choices or [])
            if value in (field.choices or []):
                widget.setCurrentText(value)
            return widget

        if field.type == "path":
            container = QWidget()
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 0, 0, 0)
            line_edit = QLineEdit(str(value or ""))
            browse_btn = QPushButton("Browse...")

            def _browse() -> None:
                folder = QFileDialog.getExistingDirectory(self, f"Choose {field.label}")
                if folder:
                    line_edit.setText(folder)

            browse_btn.clicked.connect(_browse)
            row.addWidget(line_edit)
            row.addWidget(browse_btn)
            container.line_edit = line_edit
            return container

        widget = QLineEdit(str(value) if value is not None else "")
        if field.secret:
            widget.setEchoMode(QLineEdit.EchoMode.Password)
        return widget

    def to_source_config(self) -> SourceConfig:
        options: dict[str, Any] = {}
        for key, (field, widget) in self._field_widgets.items():
            if field.type == "bool":
                options[key] = widget.isChecked()
            elif field.type == "choice":
                options[key] = widget.currentText()
            elif field.type == "path":
                options[key] = widget.line_edit.text()
            elif field.type == "int":
                try:
                    options[key] = int(widget.text())
                except ValueError:
                    options[key] = field.default
            else:
                options[key] = widget.text()
        return SourceConfig(source_id=self.source_id, enabled=self.isChecked(), options=options)


class SourcesTab(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._groups: list[_SourceGroup] = []

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        for source_id, source_cls in SOURCE_REGISTRY.items():
            source_config = config.sources.get(
                source_id, SourceConfig(source_id=source_id, enabled=False, options={})
            )
            group = _SourceGroup(source_id, source_cls, source_config)
            self._groups.append(group)
            inner_layout.addWidget(group)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def apply_to_config(self) -> None:
        for group in self._groups:
            self.config.sources[group.source_id] = group.to_source_config()
