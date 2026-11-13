import argparse
import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from . import ipc
from .config import store
from .core.engine import RotationEngine
from .ui.tray import TrayIcon
from .util.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def _parse_commands(argv: list[str]) -> list[str]:
    parser = argparse.ArgumentParser(
        prog="variety",
        description="Variety for Windows. Options control the instance that is already running.",
    )
    for command in ipc.COMMANDS:
        parser.add_argument(
            f"--{command}", dest="commands", action="append_const", const=command
        )
    return parser.parse_args(argv).commands or []


def main(argv: list[str] | None = None) -> int:
    commands = _parse_commands(sys.argv[1:] if argv is None else argv)

    setup_logging()
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)

    # A second launch hands its commands to the running instance; with no commands it
    # opens that instance's preferences, like Variety does.
    if ipc.send_commands(commands or ["preferences"]):
        return 0
    if "quit" in commands:
        return 0

    config = store.load()

    engine = RotationEngine(config)
    tray = TrayIcon(engine)
    tray.show()

    server = ipc.CommandServer(parent=app)
    server.command_received.connect(tray.handle_command)

    if engine.has_usable_sources():
        engine.rotate()
    else:
        # Nothing to show yet: let the user pick a source. Saving triggers the first rotation.
        QTimer.singleShot(0, lambda: tray.open_preferences("Sources"))
    engine.start()
    for command in commands:
        QTimer.singleShot(0, lambda c=command: tray.handle_command(c))

    exit_code = app.exec()
    store.save(config)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
