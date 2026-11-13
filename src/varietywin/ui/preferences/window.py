from typing import Callable

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout

from ...config import store
from ...config.schema import AppConfig
from .tab_display import DisplayTab
from .tab_general import GeneralTab
from .tab_overlays import OverlaysTab
from .tab_sources import SourcesTab


class PreferencesWindow(QDialog):
    def __init__(
        self,
        config: AppConfig,
        on_saved: Callable[[], None] | None = None,
        parent=None,
        initial_tab: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Variety for Windows - Preferences")
        self.resize(480, 520)
        self.config = config
        self.on_saved = on_saved

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.general_tab = GeneralTab(config)
        self.sources_tab = SourcesTab(config)
        tabs.addTab(self.general_tab, "General")
        tabs.addTab(self.sources_tab, "Sources")
        self.display_tab = DisplayTab(config)
        tabs.addTab(self.display_tab, "Display")
        self.overlays_tab = OverlaysTab(config)
        tabs.addTab(self.overlays_tab, "Quotes && clock")
        layout.addWidget(tabs)
        for index in range(tabs.count()):
            if tabs.tabText(index) == initial_tab:
                tabs.setCurrentIndex(index)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        self.general_tab.apply_to_config()
        self.sources_tab.apply_to_config()
        self.display_tab.apply_to_config()
        self.overlays_tab.apply_to_config()
        store.save(self.config)
        if self.on_saved is not None:
            self.on_saved()
        self.accept()
