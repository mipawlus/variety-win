import os
import subprocess
import sys
import winreg

from varietywin import app, ipc
from varietywin.platform_win import autostart

TEST_KEY = rf"Software\VarietyWinTests\{os.getpid()}"


def test_autostart_round_trip():
    try:
        assert not autostart.is_enabled(TEST_KEY)
        autostart.set_enabled(True, TEST_KEY)
        assert autostart.is_enabled(TEST_KEY)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEST_KEY) as key:
            value, _ = winreg.QueryValueEx(key, autostart.VALUE_NAME)
        assert value == autostart.launch_command() and "varietywin" in value
        autostart.set_enabled(False, TEST_KEY)
        autostart.set_enabled(False, TEST_KEY)  # disabling twice is fine
        assert not autostart.is_enabled(TEST_KEY)
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_KEY)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\VarietyWinTests")


def test_commands_reach_running_instance(qtbot):
    name = f"VarietyWin-test-{os.getpid()}"
    assert not ipc.send_commands(["next"], name=name, timeout_ms=100)

    server = ipc.CommandServer(name=name)
    received = []
    server.command_received.connect(received.append)

    # The sender is a second process in real use; in-process it would block on the pipe.
    client = (
        "import sys; from PySide6.QtCore import QCoreApplication; from varietywin import ipc; "
        "app = QCoreApplication([]); "
        f"sys.exit(0 if ipc.send_commands(['next', 'bogus', 'toggle-pause'], name={name!r}) else 1)"
    )
    process = subprocess.Popen([sys.executable, "-c", client])
    try:
        qtbot.waitUntil(lambda: len(received) == 2, timeout=10000)
    finally:
        assert process.wait(timeout=10) == 0
    assert received == ["next", "toggle-pause"]


def test_command_line_parsing():
    assert app._parse_commands([]) == []
    assert app._parse_commands(["--next", "--toggle-pause"]) == ["next", "toggle-pause"]
