"""一键启动:预览服务器 + 模拟(单条命令,服务器随模拟生死)。

用法:
    python start_demo.py [--ticks 3000] [--tick-ms 200] [--agent-speed 2.0] [--port 8766]

行为:
    1. 启动模拟子进程,拿到 PID。
    2. 若 8766 空闲 → 启动独立 preview_server 并开启守护模式
       (守护模拟 PID:模拟以任何形式退出,服务器自动关闭);
       端口已被占用 → 复用现有服务器(不归本命令管理)。
    3. 前台等待模拟结束(自然结束/Ctrl+C/崩溃均等待返回)。
    4. 收尾:再显式终止一次本次启动的服务器(兜底),打印页面地址。
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
    """终止本次启动的预览服务器(复用已有服务器时为 None,不动)。"""

    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
        print("[demo] 预览服务器已关闭。")
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        print("[demo] 预览服务器已强制关闭。")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command demo: preview server + simulation.")
    parser.add_argument("--ticks", type=int, default=3000)
    parser.add_argument("--tick-ms", type=int, default=200)
    parser.add_argument("--agent-speed", type=float, default=2.0)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    # 清理上一轮残留的暂停控制文件(防下一轮模拟从 tick 0 就暂停)
    ctrl_file = PROJECT_ROOT / "outputs" / "simulation_control.json"
    try:
        ctrl_file.unlink(missing_ok=True)
    except OSError:
        pass

    # 1) 先启动模拟子进程(拿到 PID,供服务器守护)
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
    print(f"[demo] 模拟启动 (pid={sim_proc.pid}): {args.ticks} ticks × {args.tick_ms}ms(约 {args.ticks * args.tick_ms / 1000:.0f}s)")

    # 2) 预览服务器:空闲则启动并守护模拟 PID;占用则复用
    proc = None
    if port_in_use(args.port):
        print(f"[demo] 端口 {args.port} 已被占用,复用现有预览服务器。")
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
        # 等待服务器就绪
        for _ in range(20):
            if port_in_use(args.port):
                break
            time.sleep(0.5)
        else:
            print(f"[demo] 预览服务器启动失败,请查看 {log_path}", file=sys.stderr)
        print(f"[demo] 预览服务器已启动(pid={proc.pid}, 守护模拟 pid={sim_proc.pid}),日志: {log_path}")

    # 自动打开浏览器(系统默认;带时间戳防缓存)
    import webbrowser

    url = f"http://127.0.0.1:{args.port}/editor/live/?v={int(time.time())}"
    webbrowser.open(url)
    print(f"[demo] 已在浏览器打开: {url}")

    # 3) 等待模拟结束(任何退出形式:自然/Ctrl+C/强杀/崩溃)
    try:
        result = sim_proc.wait()
    except KeyboardInterrupt:
        print("\n[demo] 收到 Ctrl+C:终止模拟(服务器守护将随之自动关闭)。")
        sim_proc.terminate()
        try:
            sim_proc.wait(timeout=10)
        except Exception:
            sim_proc.kill()
        _stop_preview(proc)
        sys.exit(130)
    if result != 0:
        print(f"[demo] 模拟退出码 {result}(可能已有模拟在运行,请结束后重试)", file=sys.stderr)
        _stop_preview(proc)
        sys.exit(result)

    # 4) 收尾:服务器守护线程会自动关闭;再显式终止一次作兜底
    time.sleep(1)
    _stop_preview(proc)
    print(f"[demo] 模拟结束。页面: http://127.0.0.1:{args.port}/editor/live/")
    print("[demo] 预览服务器已随模拟关闭;重新运行本命令即可再跑一轮。")


if __name__ == "__main__":
    main()
