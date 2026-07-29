"""Runtime health tracking so Workana outages are never silent."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("workana-monitor")


@dataclass
class HealthStatus:
    consecutive_failures: int = 0
    consecutive_empty: int = 0
    last_success_at: float | None = None
    last_error: str = ""
    alerted: bool = False


@dataclass
class HealthWatchdog:
    """Escalate when scraping keeps failing or returns empty listings."""

    fail_threshold: int = 5
    empty_threshold: int = 8
    alert_cooldown_seconds: int = 300
    heartbeat_path: Path | None = None
    on_alert: Callable[[str], None] | None = None
    on_fatal: Callable[[str], None] | None = None
    _state: HealthStatus = field(default_factory=HealthStatus)
    _last_alert_at: float = 0.0

    def record_success(self, *, result_count: int) -> None:
        recovered = self._state.consecutive_failures > 0 or self._state.alerted
        self._state.consecutive_failures = 0
        self._state.last_error = ""
        self._state.last_success_at = time.time()
        self._write_heartbeat(ok=True, detail=f"results={result_count}")

        if result_count <= 0:
            self._state.consecutive_empty += 1
            if self._state.consecutive_empty >= self.empty_threshold:
                self._escalate(
                    "Workana returned 0 jobs for several polls in a row. "
                    "Listings may be blocked or the category URL changed."
                )
            return

        self._state.consecutive_empty = 0
        if recovered and self._state.alerted:
            self._notify(
                "Workana monitor recovered — scraping is healthy again."
            )
            self._state.alerted = False

    def record_failure(self, error: BaseException | str) -> None:
        message = str(error)
        self._state.consecutive_failures += 1
        self._state.last_error = message
        self._write_heartbeat(ok=False, detail=message[:200])
        logger.error(
            "Health failure %s/%s: %s",
            self._state.consecutive_failures,
            self.fail_threshold,
            message,
        )

        if self._state.consecutive_failures >= self.fail_threshold:
            self._escalate(
                "Workana monitor is DOWN.\n"
                f"Failures: {self._state.consecutive_failures}\n"
                f"Last error: {message[:400]}\n"
                "Auto-restarting process to recover."
            )

    def probe_ok(self, detail: str = "startup") -> None:
        self._state.last_success_at = time.time()
        self._write_heartbeat(ok=True, detail=detail)

    def _escalate(self, message: str) -> None:
        self._notify(message)
        self._state.alerted = True
        if self.on_fatal is not None:
            self.on_fatal(message)

    def _notify(self, message: str) -> None:
        now = time.time()
        if now - self._last_alert_at < self.alert_cooldown_seconds and self._state.alerted:
            return
        self._last_alert_at = now
        logger.error("%s", message)
        if self.on_alert is not None:
            try:
                self.on_alert(message)
            except Exception:
                logger.exception("Failed to send health alert")

    def _write_heartbeat(self, *, ok: bool, detail: str) -> None:
        if self.heartbeat_path is None:
            return
        try:
            self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self.heartbeat_path.write_text(
                f"ok={int(ok)}\nupdated={stamp}\ndetail={detail}\n",
                encoding="utf-8",
            )
        except Exception:
            logger.debug("Could not write heartbeat file", exc_info=True)
