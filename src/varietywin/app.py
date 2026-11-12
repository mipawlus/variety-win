import logging
import sys

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .config import store
from .core.engine import RotationEngine
from .ui.tray import TrayIcon
from .util.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = store.load()

    local_folder_cfg = config.sources.get("local_folder")
    if local_folder_cfg is not None and not local_folder_cfg.options.get("folder"):
        folder = QFileDialog.getExistingDirectory(None, "Choose a folder with wallpaper images")
        if not folder:
            QMessageBox.warning(None, "Variety for Windows", "No folder selected. Exiting.")
            return 1
        local_folder_cfg.options["folder"] = folder
        store.save(config)

    engine = RotationEngine(config)
    tray = TrayIcon(engine)
    tray.show()

    engine.rotate()
    engine.start()

    exit_code = app.exec()
    store.save(config)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
