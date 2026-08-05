"""一键启动:预览服务器 + 模拟(单条命令)。

用法:
    python start_demo.py [--ticks 3000] [--tick-ms 200] [--agent-speed 2.0] [--port 8766]

行为:
    1. 若 8766 未被占用 → 启动独立 preview_server(no-cache,不随本命令退出);
       已占用(已有预览服务器)→ 直接复用。
    2. 前台运行模拟(单实例锁自动防重复)。
    3. 模拟结束后打印页面地址;预览服务器保持运行,可再跑模拟续看。
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


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command demo: preview server + simulation.")
    parser.add_argument("--ticks", type=int, default=3000)
    parser.add_argument("--tick-ms", type=int, default=200)
    parser.add_argument("--agent-speed", type=float, default=2.0)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    # 1) 预览服务器:未占用则独立启动(不随本命令退出)
    proc = None
    if port_in_use(args.port):
        print(f"[demo] 端口 {args.port} 已被占用,复用现有预览服务器。")
    else:
        log_path = PROJECT_ROOT / "logs" / "preview_server.log"
        log_path.parent.mkdir(exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as logf:
            proc = subprocess.Popen(
                [sys.executable, str(PROJECT_ROOT / "preview_server.py"), "--port", str(args.port)],
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
        print(f"[demo] 预览服务器已启动(pid={proc.pid}),日志: {log_path}")

    # 2) 前台运行模拟;Ctrl+C 时模拟与预览服务器一起退出
    print(f"[demo] 模拟启动: {args.ticks} ticks × {args.tick_ms}ms(约 {args.ticks * args.tick_ms / 1000:.0f}s)")
    cmd = [
        sys.executable, "-m", "simulation.main",
        "-s", "bristol_topology",
        "--agent-sim",
        "--agents-config", "configs/agents/deterministic_three_agents_bristol.json",
        "--ticks", str(args.ticks),
        "--tick-ms", str(args.tick_ms),
        "--agent-speed", str(args.agent_speed),
    ]
    preview_proc = proc  # 本次启动的预览服务器(复用已有服务器时为 None,不归我们管)
    try:
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    except KeyboardInterrupt:
        print("\n[demo] 收到 Ctrl+C:退出模拟,并关闭预览服务器。")
        if preview_proc is not None:
            try:
                preview_proc.terminate()
            except Exception:
                pass
        sys.exit(130)
    if result.returncode != 0:
        print(f"[demo] 模拟退出码 {result.returncode}(可能已有模拟在运行,请结束后重试)", file=sys.stderr)
        sys.exit(result.returncode)

    # 3) 收尾提示
    print(f"[demo] 模拟结束。页面: http://127.0.0.1:{args.port}/editor/live/")
    print(f"[demo] 预览服务器仍在运行;重新运行本命令即可再跑一轮模拟。")


if __name__ == "__main__":
    main()
