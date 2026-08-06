"""Preview static server: no-store cache control so the browser always fetches the latest files.

Usage:
    python preview_server.py [--port 8766] [--guard-pid <SIM_PID>]

--guard-pid: guardian mode - checks the PID every 2 seconds and shuts the
server down automatically once the simulation process exits (natural exit /
Ctrl+C / force kill / crash).
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _pid_alive(pid: int) -> bool:
    """Check whether a PID is alive (OpenProcess on Windows, signal 0 elsewhere)."""

    if sys.platform == "win32":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class NoCacheHandler(SimpleHTTPRequestHandler):
    """Static file handler with no-store headers (fixes browser heuristic caching of stale JS)."""

    CONTROL_PATH = PROJECT_ROOT / "outputs" / "simulation_control.json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_POST(self) -> None:
        # Control API: pause button writes/removes outputs/simulation_control.json;
        # the simulation loop checks this file every tick to implement a true pause
        if self.path.split("?")[0] != "/api/simulation/control":
            self.send_error(404, "Unknown API endpoint")
            return
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(self.path).query)
        action = query.get("action", [""])[0].strip().lower()
        try:
            if action == "toggle":
                paused = self.CONTROL_PATH.exists()
                self._set_paused(not paused)
            elif action == "pause":
                self._set_paused(True)
            elif action == "resume":
                self._set_paused(False)
            else:
                self.send_json({"ok": False, "error": "unknown action"}, status=400)
                return
            self.send_json({"ok": True, "paused": self.CONTROL_PATH.exists()})
        except OSError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def _set_paused(self, paused: bool) -> None:
        path = self.CONTROL_PATH
        if paused:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"paused": true}', encoding="utf-8")
        else:
            path.unlink(missing_ok=True)

    def send_json(self, payload: dict, status: int = 200) -> None:
        import json

        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args) -> None:  # concise log output
        pass


STATE_PATH = PROJECT_ROOT / "outputs" / "live_state.json"


def _start_guard(pid: int) -> None:
    """Guardian thread: terminates this server once the simulation process exits (covers every exit form).

    Logic: after the target PID dies, wait 3 seconds to confirm no orphan simulation
    is still writing live_state.json (the case where the wrapper was killed but a
    child process keeps running) - only shut down after the simulation is truly gone.
    """

    def guard() -> None:
        while _pid_alive(pid):
            time.sleep(2)
        # PID is dead: wait 3 seconds; if the file is still being updated an orphan simulation is running, keep the server up
        time.sleep(3)
        try:
            if STATE_PATH.exists() and time.time() - STATE_PATH.stat().st_mtime < 10:
                print("[guard] simulation child still writing data, preview server stays up.", flush=True)
                return
        except OSError:
            pass
        print(f"[guard] simulation process (pid={pid}) exited, preview server shutting down.", flush=True)
        os._exit(0)

    threading.Thread(target=guard, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the no-cache preview static server.")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--guard-pid", type=int, default=0, help="simulation PID; this server auto-closes when it exits")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), NoCacheHandler)
    if args.guard_pid:
        _start_guard(args.guard_pid)
    print(f"preview=http://{args.host}:{args.port}/editor/live/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
