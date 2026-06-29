from __future__ import annotations

import argparse
import functools
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from services.preview_service import LivePreviewService
from services.scene_service import SceneService
from .clock import SimulationClock
from .simulation_loop import SimulationLoop
from .state import SimulationState


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    args = parse_args()
    scene_service = SceneService()
    scene = scene_service.load_scene(args.scene)
    preview_service = LivePreviewService(PROJECT_ROOT / "outputs" / "live_state.json")

    if args.preview:
        start_preview_server(args.preview_port)

    state = SimulationState(scene=scene)
    loop = SimulationLoop(
        state,
        clock=SimulationClock(tick_ms=args.tick_ms),
        preview_service=preview_service,
    )
    loop.run(args.ticks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RAN behavior simulation loop.")
    parser.add_argument("-s", "--scene", default="potions_teacher_office", help="registered scene name")
    parser.add_argument("--ticks", type=int, default=200, help="number of ticks to run")
    parser.add_argument("--tick-ms", type=int, default=500, help="milliseconds per tick")
    parser.add_argument("-p", "--preview", action="store_true", help="open the live preview page")
    parser.add_argument("--preview-port", type=int, default=8765, help="preview server port")
    return parser.parse_args()


def start_preview_server(port: int) -> None:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/editor/live/"
    print(f"preview={url}", flush=True)
    webbrowser.open(url)


if __name__ == "__main__":
    main()
