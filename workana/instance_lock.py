"""Ensure only one Workana monitor process runs at a time."""

from __future__ import annotations

import atexit
import sys
from pathlib import Path

LOCK_PATH = Path(__file__).resolve().parents[1] / "data" / "monitor.lock"
_lock_handle = None


def acquire_singleton_lock(path: Path = LOCK_PATH) -> None:
    """Exit if another monitor already holds the lock."""
    global _lock_handle

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+", encoding="utf-8")
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            handle.write("0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        print(
            f"Another Workana monitor is already running (lock: {path}). Exiting.",
            flush=True,
        )
        raise SystemExit(0)

    handle.seek(0)
    handle.truncate()
    handle.write(str(__import__("os").getpid()))
    handle.flush()
    _lock_handle = handle
    atexit.register(release_singleton_lock)


def release_singleton_lock() -> None:
    global _lock_handle
    if _lock_handle is None:
        return
    try:
        if sys.platform == "win32":
            import msvcrt

            _lock_handle.seek(0)
            msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        _lock_handle.close()
    except OSError:
        pass
    _lock_handle = None
