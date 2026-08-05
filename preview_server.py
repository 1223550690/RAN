"""预览静态服务器:no-store 缓存控制,浏览器永远取最新文件。

用法:
    python preview_server.py [--port 8766] [--guard-pid <模拟PID>]

--guard-pid:守护模式——每 2 秒检查该 PID 是否存活,
模拟进程以任何形式退出(自然结束/Ctrl+C/强杀/崩溃)后自动关闭本服务器。
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
    """检查 PID 是否存活(Windows 用 OpenProcess,其他平台用信号 0)。"""

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
    """带 no-store 头的静态文件服务(解决浏览器启发式缓存旧 JS 的问题)。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args) -> None:  # 精简日志
        pass


STATE_PATH = PROJECT_ROOT / "outputs" / "live_state.json"


def _start_guard(pid: int) -> None:
    """守护线程:模拟进程退出后终止本服务器(覆盖任何退出形式)。

    逻辑:目标 PID 死亡后,再确认 3 秒内无孤儿模拟继续写 live_state.json
    (wrapper 被杀而子进程仍在跑的场景)→ 确认模拟真的退出才关闭自己。
    """

    def guard() -> None:
        while _pid_alive(pid):
            time.sleep(2)
        # pid 已死:等 3 秒,若文件仍在更新说明有孤儿模拟还在跑,不关
        time.sleep(3)
        try:
            if STATE_PATH.exists() and time.time() - STATE_PATH.stat().st_mtime < 10:
                print("[guard] 检测到模拟子进程仍在写数据,预览服务器保持运行。", flush=True)
                return
        except OSError:
            pass
        print(f"[guard] 模拟进程 (pid={pid}) 已退出,预览服务器自动关闭。", flush=True)
        os._exit(0)

    threading.Thread(target=guard, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the no-cache preview static server.")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--guard-pid", type=int, default=0, help="模拟进程 PID;其退出后本服务器自动关闭")
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
