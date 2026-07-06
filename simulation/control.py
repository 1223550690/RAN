from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock


class SimulationControl:
    """仿真运行控制器。

    输入:
    - simulation loop 写入的日志行。
    - preview 页面发来的 pause/resume/export 指令。

    输出:
    - paused 状态。
    - 导出的日志文件路径。
    """

    def __init__(self, *, log_dir: str | Path = "log") -> None:
        self.log_dir = Path(log_dir)
        self.paused = False
        self._logs: list[str] = []
        self._lock = Lock()

    def set_paused(self, paused: bool) -> dict:
        """设置暂停状态。

        输入:
        - paused: True 暂停，False 继续。

        输出:
        - 当前控制状态。
        """

        with self._lock:
            self.paused = bool(paused)
            state = "paused" if self.paused else "running"
            self._logs.append(f"control={state}")
            return self.snapshot_unlocked()

    def toggle_paused(self) -> dict:
        """切换暂停/继续状态。"""

        with self._lock:
            self.paused = not self.paused
            state = "paused" if self.paused else "running"
            self._logs.append(f"control={state}")
            return self.snapshot_unlocked()

    def append_log(self, line: str) -> None:
        """记录一行运行日志。"""

        with self._lock:
            self._logs.append(str(line))
            if len(self._logs) > 20000:
                del self._logs[:-20000]

    def export_logs(self) -> dict:
        """导出当前为止的所有日志信息。

        输出:
        - path: 导出的日志文件路径。
        - line_count: 导出行数。
        """

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
        """返回当前控制状态。"""

        with self._lock:
            return self.snapshot_unlocked()

    def snapshot_unlocked(self) -> dict:
        return {
            "paused": self.paused,
            "log_count": len(self._logs),
        }
