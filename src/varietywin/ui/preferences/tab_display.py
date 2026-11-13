import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...config.schema import AppConfig
from ...platform_win import wallpaper_multi
from ...sources.registry import SOURCE_REGISTRY

logger = logging.getLogger(__name__)

ANY_SOURCE_LABEL = "Any enabled source"


class DisplayTab(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        layout = QVBoxLayout(self)

        effects = QGroupBox("Effects")
        effects_form = QFormLayout(effects)
        self.grayscale_check = QCheckBox("Grayscale")
        self.grayscale_check.setChecked(config.filters.grayscale)
        effects_form.addRow("", self.grayscale_check)
        self.blur_check = QCheckBox("Blur")
        self.blur_check.setChecked(config.filters.blur)
        effects_form.addRow("", self.blur_check)

        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(20, 150)
        self.brightness_slider.setValue(round(config.filters.brightness * 100))
        self.brightness_label = QLabel()
        self.brightness_slider.valueChanged.connect(self._update_brightness_label)
        self._update_brightness_label(self.brightness_slider.value())
        brightness_row = QHBoxLayout()
        brightness_row.addWidget(self.brightness_slider)
        brightness_row.addWidget(self.brightness_label)
        effects_form.addRow("Brightness", brightness_row)
        layout.addWidget(effects)

        requirements = QGroupBox("Image requirements")
        requirements_form = QFormLayout(requirements)
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(0, 100)
        self.min_size_spin.setSingleStep(10)
        self.min_size_spin.setSuffix(" % of screen")
        self.min_size_spin.setSpecialValueText("Any size")
        self.min_size_spin.setValue(config.requirements.min_size_percent)
        requirements_form.addRow("Minimum size", self.min_size_spin)
        self.orientation_check = QCheckBox("Only images that match the screen orientation")
        self.orientation_check.setChecked(config.requirements.match_orientation)
        requirements_form.addRow("", self.orientation_check)
        layout.addWidget(requirements)

        monitors_box = QGroupBox("Monitors")
        monitors_form = QFormLayout(monitors_box)
        self.per_monitor_check = QCheckBox("Different wallpaper on each monitor")
        self.per_monitor_check.setChecked(not config.monitors.same_on_all_monitors)
        monitors_form.addRow("", self.per_monitor_check)

        try:
            monitors = wallpaper_multi.list_monitors()
        except Exception:
            logger.exception("Could not enumerate monitors")
            monitors = []

        self._source_combos: dict[str, QComboBox] = {}
        for monitor in monitors:
            combo = QComboBox()
            combo.addItem(ANY_SOURCE_LABEL, "")
            for source_id, source_cls in SOURCE_REGISTRY.items():
                combo.addItem(source_cls.display_name, source_id)
            index = combo.findData(config.monitors.per_monitor_source_ids.get(monitor.id, ""))
            combo.setCurrentIndex(max(index, 0))
            self._source_combos[monitor.id] = combo
            monitors_form.addRow(monitor.label, combo)

        if len(monitors) < 2:
            self.per_monitor_check.setEnabled(False)
            monitors_form.addRow("", QLabel("Only one monitor detected."))

        self.per_monitor_check.toggled.connect(self._update_combos_enabled)
        self._update_combos_enabled(self.per_monitor_check.isChecked())
        layout.addWidget(monitors_box)
        layout.addStretch(1)

    def _update_brightness_label(self, value: int) -> None:
        self.brightness_label.setText(f"{value}%")

    def _update_combos_enabled(self, enabled: bool) -> None:
        for combo in self._source_combos.values():
            combo.setEnabled(enabled)

    def apply_to_config(self) -> None:
        self.config.filters.grayscale = self.grayscale_check.isChecked()
        self.config.filters.blur = self.blur_check.isChecked()
        self.config.filters.brightness = self.brightness_slider.value() / 100
        self.config.requirements.min_size_percent = self.min_size_spin.value()
        self.config.requirements.match_orientation = self.orientation_check.isChecked()
        self.config.monitors.same_on_all_monitors = not self.per_monitor_check.isChecked()
        for monitor_id, combo in self._source_combos.items():
            source_id = combo.currentData()
            if source_id:
                self.config.monitors.per_monitor_source_ids[monitor_id] = source_id
            else:
                self.config.monitors.per_monitor_source_ids.pop(monitor_id, None)
