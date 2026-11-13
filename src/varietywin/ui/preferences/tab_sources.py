from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config.schema import AppConfig, SourceConfig
from ...sources.base import ConfigField
from ...sources.registry import SOURCE_REGISTRY, get_source_class


def entry_label(entry: SourceConfig) -> str:
    """How a source entry is shown in lists, e.g. "Wallhaven — forest, space"."""
    source_cls = get_source_class(entry.source_id)
    if source_cls is None:
        return f"{entry.source_id} (unknown source)"
    details = source_cls(entry.options).describe()
    return f"{source_cls.display_name} — {details}" if details else source_cls.display_name


class SourceOptionsForm(QWidget):
    """Editing widgets for one source's options, built from its `config_fields()`."""

    def __init__(self, source_cls, options: dict[str, Any], parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._field_widgets: dict[str, tuple[ConfigField, QWidget]] = {}

        for field in source_cls.config_fields():
            widget = self._build_widget(field, options.get(field.key, field.default))
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

    def options(self) -> dict[str, Any]:
        options: dict[str, Any] = {}
        for key, (field, widget) in self._field_widgets.items():
            if field.type == "bool":
                options[key] = widget.isChecked()
            elif field.type == "choice":
                options[key] = widget.currentText()
            elif field.type == "path":
                options[key] = widget.line_edit.text().strip()
            elif field.type == "int":
                try:
                    options[key] = int(widget.text())
                except ValueError:
                    options[key] = field.default
            else:
                options[key] = widget.text().strip()
        return options


class SourceDialog(QDialog):
    def __init__(self, source_cls, options: dict[str, Any], adding: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{'Add' if adding else 'Edit'} source: {source_cls.display_name}")
        self.setMinimumWidth(440)
        self.source_cls = source_cls

        layout = QVBoxLayout(self)
        self.form = SourceOptionsForm(source_cls, options)
        layout.addWidget(self.form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        problems = self.source_cls(self.form.options()).validate_config()
        if problems:
            QMessageBox.warning(self, self.windowTitle(), "\n".join(problems))
            return
        self.accept()


class SourcesTab(QWidget):
    """A list of source entries. The same kind of source can be added several times,
    each with its own tags, and switched on and off independently."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._entries = [entry.model_copy(deep=True) for entry in config.sources]

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Wallpapers are picked at random from the ticked sources."))

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _item: self._edit())
        self.list.currentRowChanged.connect(lambda _row: self._update_buttons())
        layout.addWidget(self.list)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add")
        add_menu = QMenu(self.add_button)
        for source_id, source_cls in SOURCE_REGISTRY.items():
            add_menu.addAction(source_cls.display_name, lambda s=source_id: self._add(s))
        self.add_button.setMenu(add_menu)
        self.edit_button = QPushButton("Edit...")
        self.edit_button.clicked.connect(lambda: self._edit())
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(lambda: self._remove())
        for button in (self.add_button, self.edit_button, self.remove_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        for entry in self._entries:
            self._append_item(entry)
        self._update_buttons()

    def _append_item(self, entry: SourceConfig) -> None:
        item = QListWidgetItem(entry_label(entry))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if entry.enabled else Qt.CheckState.Unchecked)
        self.list.addItem(item)

    def _update_buttons(self) -> None:
        row = self.list.currentRow()
        selected = 0 <= row < len(self._entries)
        editable = selected and bool(
            (cls := get_source_class(self._entries[row].source_id)) and cls.config_fields()
        )
        self.edit_button.setEnabled(editable)
        self.remove_button.setEnabled(selected)

    def _ask_options(self, entry: SourceConfig, adding: bool) -> dict[str, Any] | None:
        dialog = SourceDialog(get_source_class(entry.source_id), entry.options, adding, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.form.options()

    def _add(self, source_id: str) -> None:
        source_cls = SOURCE_REGISTRY[source_id]
        entry = SourceConfig(
            source_id=source_id,
            options={field.key: field.default for field in source_cls.config_fields()},
        )
        if source_cls.config_fields():
            options = self._ask_options(entry, adding=True)
            if options is None:
                return
            entry.options = options
        self._entries.append(entry)
        self._append_item(entry)
        self.list.setCurrentRow(len(self._entries) - 1)

    def _edit(self) -> None:
        row = self.list.currentRow()
        if not self.edit_button.isEnabled() or row < 0:
            return
        entry = self._entries[row]
        options = self._ask_options(entry, adding=False)
        if options is not None:
            entry.options = options
            self.list.item(row).setText(entry_label(entry))

    def _remove(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._entries):
            del self._entries[row]
            self.list.takeItem(row)
            self._update_buttons()

    def apply_to_config(self) -> None:
        for row, entry in enumerate(self._entries):
            entry.enabled = self.list.item(row).checkState() == Qt.CheckState.Checked
        self.config.sources = [entry.model_copy(deep=True) for entry in self._entries]
