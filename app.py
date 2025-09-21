# app.py
from __future__ import annotations
import sys
from PyQt6 import QtWidgets
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from main_window import MainWindow

APP_NAME = "LCARSlite Weather and Vacation"
APP_KEY  = "com.lcarslite.weather.vacation.singleinstance"


class SingleInstance(QLocalServer):
    """
    Primäre Instanz: lauscht auf QLocalServer (APP_KEY).
    Sekundäre Instanz: verbindet sich kurz, sendet 'ACTIVATE' und beendet sich.
    """
    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self._key = key
        # evtl. Leiche vom letzten Lauf entfernen
        QLocalServer.removeServer(self._key)
        self.is_primary = self.listen(self._key)
        if self.is_primary:
            self.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self):
        while self.hasPendingConnections():
            sock = self.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read_socket(s))

    def _read_socket(self, sock: QLocalSocket):
        try:
            data = bytes(sock.readAll()).decode("utf-8", "ignore").strip()
            if data == "ACTIVATE":
                # vorhandenes Fenster aktivieren
                for widget in QtWidgets.QApplication.topLevelWidgets():
                    if isinstance(widget, MainWindow):
                        if widget.isMinimized():
                            widget.showNormal()
                        widget.raise_()
                        widget.activateWindow()
                        break
        finally:
            sock.disconnectFromServer()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(True)

    # Single Instance
    server = SingleInstance(APP_KEY)
    if not server.is_primary:
        # Zweitinstanz → Aktivierungsnachricht senden, dann beenden
        sock = QLocalSocket()
        sock.connectToServer(APP_KEY)
        if sock.waitForConnected(500):
            sock.write(b"ACTIVATE\n")
            sock.flush()
            sock.waitForBytesWritten(500)
        sys.exit(0)

    # Hauptfenster
    w = MainWindow()
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
