"""One-shot launcher: preview server + simulation (single command, server lifetime tied to the simulation).

Usage:
    python start_demo.py [--ticks 3000] [--tick-ms 200] [--agent-speed 2.0] [--port 8766]

Behaviour:
    1. Start the simulation subprocess and capture its PID.
    2. If port 8766 is free, start an independent preview_server in guardian mode
       (guarding the simulation PID: the server closes automatically no matter
       how the simulation exits); if the port is already taken, reuse the
       existing server (not managed by this command).
    3. Wait in the foreground for the simulation to finish (natural exit /
       Ctrl+C / crash all return).
    4. Cleanup: explicitly terminate the server started here once more (safety
       net) and print the page URL.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def port_in_use(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _stop_preview(proc) -> None:
    """Terminate the preview server started by this launcher (None when reusing an existing server)."""

    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
        print("[demo] preview server closed.")
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        print("[demo] preview server force-closed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command demo: preview server + simulation.")
    parser.add_argument("--ticks", type=int, default=3000)
    parser.add_argument("--tick-ms", type=int, default=200)
    parser.add_argument("--agent-speed", type=float, default=2.0)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    # clear a stale pause control file from a previous run (prevents the next simulation starting paused at tick 0)
    ctrl_file = PROJECT_ROOT / "outputs" / "simulation_control.json"
    try:
        ctrl_file.unlink(missing_ok=True)
    except OSError:
        pass

    # 1) start the simulation subprocess first (capture its PID for the server guardian)
    cmd = [
        sys.executable, "-m", "simulation.main",
        "-s", "bristol_topology",
        "--agent-sim",
        "--agents-config", "configs/agents/deterministic_three_agents_bristol.json",
        "--ticks", str(args.ticks),
        "--tick-ms", str(args.tick_ms),
        "--agent-speed", str(args.agent_speed),
    ]
    sim_proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
    print(f"[demo] simulation started (pid={sim_proc.pid}): {args.ticks} ticks x {args.tick_ms}ms (~{args.ticks * args.tick_ms / 1000:.0f}s)")

    # 2) preview server: start with guardian if the port is free; otherwise reuse
    proc = None
    if port_in_use(args.port):
        print(f"[demo] port {args.port} already in use, reusing the existing preview server.")
    else:
        log_path = PROJECT_ROOT / "logs" / "preview_server.log"
        log_path.parent.mkdir(exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as logf:
            proc = subprocess.Popen(
                [sys.executable, str(PROJECT_ROOT / "preview_server.py"),
                 "--port", str(args.port), "--guard-pid", str(sim_proc.pid)],
                cwd=str(PROJECT_ROOT),
                stdout=logf,
                stderr=logf,
                close_fds=True,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        # wait for the server to become ready
        for _ in range(20):
            if port_in_use(args.port):
                break
            time.sleep(0.5)
        else:
            print(f"[demo] failed to start preview server, see {log_path}", file=sys.stderr)
        print(f"[demo] preview server started (pid={proc.pid}, guarding sim pid={sim_proc.pid}), log: {log_path}")

    # auto-open the browser (system default; timestamped URL defeats caching)
    import webbrowser

    url = f"http://127.0.0.1:{args.port}/editor/live/?v={int(time.time())}"
    webbrowser.open(url)
    print(f"[demo] opened in browser: {url}")

    # 3) wait for the simulation to end (any exit form: natural / Ctrl+C / force kill / crash)
    try:
        result = sim_proc.wait()
    except KeyboardInterrupt:
        print("\n[demo] Ctrl+C received: terminating the simulation (the guarded server will close with it).")
        sim_proc.terminate()
        try:
            sim_proc.wait(timeout=10)
        except Exception:
            sim_proc.kill()
        _stop_preview(proc)
        sys.exit(130)
    if result != 0:
        print(f"[demo] simulation exit code {result} (a simulation may already be running; stop it and retry)", file=sys.stderr)
        _stop_preview(proc)
        sys.exit(result)

    # 4) cleanup: the guardian thread closes the server automatically; terminate once more as a safety net
    time.sleep(1)
    _stop_preview(proc)
    print(f"[demo] simulation finished. Page: http://127.0.0.1:{args.port}/editor/live/")
    print("[demo] preview server closed with the simulation; rerun this command for another round.")


if __name__ == "__main__":
    main()
