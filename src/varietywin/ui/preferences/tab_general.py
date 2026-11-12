from PySide6.QtWidgets import QCheckBox, QFormLayout, QSpinBox, QWidget

from ...config.schema import AppConfig


class GeneralTab(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config

        layout = QFormLayout(self)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 24 * 60 * 60)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setValue(config.general.rotation_interval_seconds)
        layout.addRow("Rotation interval", self.interval_spin)

        self.paused_check = QCheckBox("Pause automatic rotation")
        self.paused_check.setChecked(config.general.paused)
        layout.addRow("", self.paused_check)

    def apply_to_config(self) -> None:
        self.config.general.rotation_interval_seconds = self.interval_spin.value()
        self.config.general.paused = self.paused_check.isChecked()
