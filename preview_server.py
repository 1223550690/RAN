"""预览静态服务器:no-store 缓存控制,浏览器永远取最新文件。

用法:python preview_server.py [--port 8766]
页面:http://127.0.0.1:8766/editor/live/
"""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the no-cache preview static server.")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), NoCacheHandler)
    print(f"preview=http://{args.host}:{args.port}/editor/live/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
