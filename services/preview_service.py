from __future__ import annotations

import json
import os
import time
from pathlib import Path


class LivePreviewService:
    def __init__(
        self,
        output_path: str | Path = "outputs/live_state.json",
        *,
        replace_retries: int = 5,
        retry_sleep_seconds: float = 0.025,
    ) -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.replace_retries = replace_retries
        self.retry_sleep_seconds = retry_sleep_seconds

    def write_state(
        self,
        *,
        tick: int,
        now_seconds: float,
        scene,
        agents: list | None = None,
        ran_requests: list[dict] | None = None,
        console: list[str] | None = None,
    ) -> None:
        payload = {
            "tick": tick,
            "now_seconds": now_seconds,
            "scene": scene.to_dict(),
            "agents": [agent.to_dict() for agent in agents or []],
            "ran_requests": list(ran_requests or []),
            "console": list(console or [])[-80:],
        }
        temp_path = self.output_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.replace_with_retry(temp_path)

    def replace_with_retry(self, temp_path: Path) -> None:
        for attempt in range(self.replace_retries + 1):
            try:
                os.replace(temp_path, self.output_path)
                return
            except PermissionError:
                if attempt >= self.replace_retries:
                    self.cleanup_temp_file(temp_path)
                    return
                time.sleep(self.retry_sleep_seconds)

    @staticmethod
    def cleanup_temp_file(temp_path: Path) -> None:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
