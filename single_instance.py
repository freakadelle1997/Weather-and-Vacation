# single_instance.py
from __future__ import annotations
import os, tempfile, fcntl
from pathlib import Path
from typing import Optional

LOCKFILE_PATH = str(Path(tempfile.gettempdir()) / "wetterdaten_app.lock")

def acquire_single_instance_lock() -> Optional[int]:
    try:
        fd = os.open(LOCKFILE_PATH, os.O_CREAT | os.O_RDWR)
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except Exception:
        return None
