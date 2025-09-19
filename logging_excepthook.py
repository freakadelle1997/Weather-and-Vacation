# logging_excepthook.py
from __future__ import annotations
import sys, logging, traceback
from pathlib import Path

LOG_DIR = Path.home() / "Library" / "Logs" / "Wetterdaten"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def install_excepthook():
    def _hook(exctype, value, tb):
        msg = "".join(traceback.format_exception(exctype, value, tb))
        logging.error("Uncaught exception:\n%s", msg)
        try:
            from PyQt6 import QtWidgets
            QtWidgets.QMessageBox.critical(
                None,
                "Unerwarteter Fehler",
                "Die Anwendung hat einen Fehler abgefangen und bleibt geöffnet.\n\n"
                f"Details wurden nach {LOG_FILE} geschrieben.\n\n"
                f"{str(value)}"
            )
        except Exception:
            pass
    sys.excepthook = _hook
