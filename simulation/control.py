from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock


class SimulationControl:
    """Project implementation detail."""

    def __init__(self, *, log_dir: str | Path = "log") -> None:
        self.log_dir = Path(log_dir)
        self.paused = False
        self._logs: list[str] = []
        self._lock = Lock()

    def set_paused(self, paused: bool) -> dict:
        """Project implementation detail."""

        with self._lock:
            self.paused = bool(paused)
            state = "paused" if self.paused else "running"
            self._logs.append(f"control={state}")
            return self.snapshot_unlocked()

    def toggle_paused(self) -> dict:
        """Project implementation detail."""

        with self._lock:
            self.paused = not self.paused
            state = "paused" if self.paused else "running"
            self._logs.append(f"control={state}")
            return self.snapshot_unlocked()

    def append_log(self, line: str) -> None:
        """Project implementation detail."""

        with self._lock:
            self._logs.append(str(line))
            if len(self._logs) > 20000:
                del self._logs[:-20000]

    def export_logs(self) -> dict:
        """Project implementation detail."""

        with self._lock:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.log_dir / f"ran_simulation_{timestamp}.log"
            lines = list(self._logs)
            path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            self._logs.append(f"control=export path={path}")
            return {
                "path": str(path),
                "line_count": len(lines),
                "control": self.snapshot_unlocked(),
            }

    def snapshot(self) -> dict:
        """Project implementation detail."""

        with self._lock:
            return self.snapshot_unlocked()

    def snapshot_unlocked(self) -> dict:
        return {
            "paused": self.paused,
            "log_count": len(self._logs),
        }
