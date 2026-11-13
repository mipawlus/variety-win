"""Single-instance guard and command channel, so `variety --next` controls the running app."""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

SERVER_NAME = "VarietyWin-ipc"

COMMANDS = (
    "next",
    "previous",
    "pause",
    "resume",
    "toggle-pause",
    "favorite",
    "trash",
    "preferences",
    "quit",
)


def send_commands(commands: list[str], name: str = SERVER_NAME, timeout_ms: int = 500) -> bool:
    """Send commands to a running instance. Returns False if none is running."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(timeout_ms):
        return False
    socket.write(("\n".join(commands) + "\n").encode("utf-8"))
    socket.waitForBytesWritten(timeout_ms)
    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        socket.waitForDisconnected(timeout_ms)
    return True


class CommandServer(QObject):
    command_received = Signal(str)

    def __init__(self, name: str = SERVER_NAME, parent=None):
        super().__init__(parent)
        self._sockets: set[QLocalSocket] = set()
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        if not self._server.listen(name):
            logger.warning("Could not start command server: %s", self._server.errorString())

    def _on_new_connection(self) -> None:
        while (socket := self._server.nextPendingConnection()) is not None:
            # Keep our own reference: the socket must outlive the signals it still has to emit.
            self._sockets.add(socket)
            socket.readyRead.connect(self._on_ready_read)
            socket.disconnected.connect(self._on_disconnected)
            self._read(socket)

    def _on_ready_read(self) -> None:
        self._read(self.sender())

    def _on_disconnected(self) -> None:
        socket = self.sender()
        self._read(socket)
        self._sockets.discard(socket)
        socket.deleteLater()

    def close(self) -> None:
        self._server.close()
        for socket in list(self._sockets):
            socket.abort()

    def _read(self, socket: QLocalSocket) -> None:
        while socket.bytesAvailable():
            command = bytes(socket.readLine().data()).decode("utf-8", "replace").strip()
            if command in COMMANDS:
                self.command_received.emit(command)
            elif command:
                logger.warning("Ignoring unknown command: %s", command)
