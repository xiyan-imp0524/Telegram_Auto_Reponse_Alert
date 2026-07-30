"""Keep the Workana monitor running — restarts automatically if it stops."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
MAIN = ROOT / "main.py"
MIN_DELAY = 5
MAX_DELAY = 60
HEARTBEAT = ROOT / "data" / "heartbeat.txt"


def run() -> None:
    delay = MIN_DELAY
    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Workana monitor...", flush=True)
        process = subprocess.Popen(
            [PYTHON, str(MAIN)],
            cwd=str(ROOT),
            env={**dict(os.environ), "PYTHONPATH": str(ROOT)},
        )
        exit_code = process.wait()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{stamp}] Monitor exited ({exit_code}). Restarting in {delay}s...",
            flush=True,
        )
        try:
            HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
            HEARTBEAT.write_text(
                f"ok=0\nupdated={stamp}\ndetail=process_exit_{exit_code}\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        # Faster restart on intentional health exit (code 2); back off on crash loops.
        if exit_code == 2:
            delay = MIN_DELAY
        else:
            delay = min(MAX_DELAY, max(MIN_DELAY, delay * 2))
        time.sleep(delay)


if __name__ == "__main__":
    run()
