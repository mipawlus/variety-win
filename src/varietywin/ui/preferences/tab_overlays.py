from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config.schema import AppConfig


class OverlaysTab(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        layout = QVBoxLayout(self)

        quotes_box = QGroupBox("Quotes")
        quotes_form = QFormLayout(quotes_box)
        self.quotes_check = QCheckBox("Show a quote on the wallpaper")
        self.quotes_check.setChecked(config.quotes.enabled)
        quotes_form.addRow("", self.quotes_check)

        self.quotes_file_edit = QLineEdit(config.quotes.file)
        self.quotes_file_edit.setPlaceholderText("Built-in quotes")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_quotes_file)
        file_row = QHBoxLayout()
        file_row.addWidget(self.quotes_file_edit)
        file_row.addWidget(browse)
        quotes_form.addRow("Quotes file", file_row)
        hint = QLabel("A text file with one quote per line, optionally ending with  -- Author")
        hint.setWordWrap(True)
        quotes_form.addRow("", hint)
        layout.addWidget(quotes_box)

        clock_box = QGroupBox("Clock")
        clock_form = QFormLayout(clock_box)
        self.clock_check = QCheckBox("Show a clock on the wallpaper")
        self.clock_check.setChecked(config.clock.enabled)
        clock_form.addRow("", self.clock_check)
        self.date_check = QCheckBox("Show the date under the clock")
        self.date_check.setChecked(config.clock.show_date)
        clock_form.addRow("", self.date_check)
        layout.addWidget(clock_box)

        layout.addStretch(1)

    def _browse_quotes_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a quotes file", "", "Text files (*.txt);;All files (*)"
        )
        if path:
            self.quotes_file_edit.setText(path)

    def apply_to_config(self) -> None:
        self.config.quotes.enabled = self.quotes_check.isChecked()
        self.config.quotes.file = self.quotes_file_edit.text().strip()
        self.config.clock.enabled = self.clock_check.isChecked()
        self.config.clock.show_date = self.date_check.isChecked()
