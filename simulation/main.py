from __future__ import annotations

import argparse
import functools
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from services.map_service import MapService
from services.preview_service import LivePreviewService
from services.scene_service import SceneService
from ran import RanEngine
from .control import SimulationControl
from .clock import SimulationClock
from .simulation_loop import SimulationLoop
from .state import SimulationState


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    args = parse_args()
    scene_service = SceneService()
    scene = scene_service.load_scene(args.scene)
    preview_service = LivePreviewService(PROJECT_ROOT / "outputs" / "live_state.json")
    control = SimulationControl(log_dir=PROJECT_ROOT / "log")

    if args.console:
        run_console(scene)
        return

    if args.ran_mvp:
        if args.ran_mvp_mode == "tick":
            if args.preview:
                start_preview_server(args.preview_port, scene, control)
            run_ran_mvp_tick(scene, args, preview_service, control)
            return
        run_ran_mvp_aggregate(scene, args.ticks)
        return

    if args.preview:
        start_preview_server(args.preview_port, scene, control)

    state = SimulationState(scene=scene)
    loop = SimulationLoop(
        state,
        clock=SimulationClock(tick_ms=args.tick_ms),
        preview_service=preview_service,
        control=control,
    )
    loop.run(args.ticks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RAN behavior simulation loop.")
    parser.add_argument("-s", "--scene", default="potions_teacher_office", help="registered scene name")
    parser.add_argument("--ticks", type=int, default=200, help="number of ticks to run")
    parser.add_argument("--tick-ms", type=int, default=500, help="milliseconds per tick")
    parser.add_argument("-p", "--preview", action="store_true", help="open the live preview page")
    parser.add_argument("--preview-port", type=int, default=8766, help="preview server port")
    parser.add_argument("--console", action="store_true", help="open an interactive map query console")
    parser.add_argument("--ran-mvp", action="store_true", help="run the fixed RAN MVP upload scenario")
    parser.add_argument(
        "--ran-mvp-mode",
        choices=["aggregate", "tick"],
        default="aggregate",
        help="RAN MVP mode: aggregate summary or per-tick simulation",
    )
    return parser.parse_args()


def run_ran_mvp_aggregate(scene, tick: int) -> None:
    engine = RanEngine(scene)
    result = engine.run_agent_upload_demo(tick=1, max_ticks=max(5000, tick))
    summary = result["result"]
    qos = summary["qos"]
    requested = summary["requested_bytes"]
    delivered = summary["delivered_bytes"]
    remaining_ratio = max(0, requested - delivered) / requested if requested else 0.0
    print(
        "ran_mvp="
        f"service_id={summary['service_id']} "
        f"delivered={summary['delivered_bytes']} "
        f"undelivered={summary['failed_bytes']} "
        f"tick_throughput_mbps={qos['throughput_mbps']:.3f} "
        f"latency_ms={qos['latency_ms']:.3f} "
        f"remaining_ratio={remaining_ratio:.6f} "
        f"loss_rate={qos['packet_loss_rate']:.6f}",
        flush=True,
    )


def run_ran_mvp_tick(
    scene,
    args: argparse.Namespace,
    preview_service: LivePreviewService,
    control: SimulationControl,
) -> None:
    engine = RanEngine(scene)
    state = SimulationState(scene=scene)
    loop = SimulationLoop(
        state,
        clock=SimulationClock(tick_ms=args.tick_ms),
        preview_service=preview_service,
        ran_scenario=engine.build_upload_scenario(),
        control=control,
    )
    loop.run(args.ticks)


def run_console(scene) -> None:
    map_service = MapService()
    print(f"map console scene={scene.node_id}", flush=True)
    print("commands: area <x> <y> | pos <object_id> | walls <x1> <y1> <x2> <y2> | help | quit", flush=True)
    while True:
        try:
            raw = input("map> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not raw:
            continue
        parts = raw.split()
        command = parts[0].lower()
        if command in {"quit", "exit", "q"}:
            return
        if command == "help":
            print("area <x> <y>      query area at map coordinate", flush=True)
            print("pos <object_id>   query object bounds/center by id", flush=True)
            print("walls <x1> <y1> <x2> <y2>   query walls crossed by a coordinate line", flush=True)
            print("quit              exit console", flush=True)
            continue
        if command == "area" and len(parts) == 3:
            try:
                result = map_service.get_area_at(scene, float(parts[1]), float(parts[2]))
            except ValueError:
                print("invalid coordinate", flush=True)
                continue
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            continue
        if command == "pos" and len(parts) == 2:
            result = map_service.get_object_position(scene, parts[1])
            print(json.dumps(result or {"error": "not found", "object_id": parts[1]}, ensure_ascii=False, indent=2), flush=True)
            continue
        if command == "walls" and len(parts) == 5:
            try:
                result = map_service.get_walls_between(
                    scene,
                    (float(parts[1]), float(parts[2])),
                    (float(parts[3]), float(parts[4])),
                )
            except ValueError:
                print("invalid coordinate", flush=True)
                continue
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            continue
        print("unknown command. use: area <x> <y> | pos <object_id> | walls <x1> <y1> <x2> <y2> | help | quit", flush=True)


def start_preview_server(port: int, scene, control: SimulationControl) -> None:
    handler = functools.partial(MapPreviewRequestHandler, scene=scene, control=control, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/editor/live/"
    print(f"preview={url}", flush=True)
    webbrowser.open(url)


class MapPreviewRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, scene, control: SimulationControl, **kwargs):
        self.scene = scene
        self.control = control
        self.map_service = MapService()
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/map/query":
            self.handle_map_query(parsed.query)
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/simulation/control":
            self.handle_control(parsed.query)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")

    def handle_map_query(self, raw_query: str) -> None:
        query = parse_qs(raw_query)
        command = query.get("command", [""])[0].strip()
        try:
            result = self.execute_map_command(command)
            self.send_json(result)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)

    def handle_control(self, raw_query: str) -> None:
        query = parse_qs(raw_query)
        action = query.get("action", [""])[0].strip().lower()
        if action == "toggle_pause":
            self.send_json({"ok": True, "control": self.control.toggle_paused()})
            return
        if action == "pause":
            self.send_json({"ok": True, "control": self.control.set_paused(True)})
            return
        if action == "resume":
            self.send_json({"ok": True, "control": self.control.set_paused(False)})
            return
        if action == "export_logs":
            self.send_json({"ok": True, "export": self.control.export_logs()})
            return
        self.send_json({"ok": False, "error": "unknown control action"}, status=400)

    def execute_map_command(self, command: str) -> dict:
        parts = command.split()
        if not parts:
            raise ValueError("empty command")
        name = parts[0].lower()
        if name == "area" and len(parts) == 3:
            try:
                return self.map_service.get_area_at(self.scene, float(parts[1]), float(parts[2]))
            except ValueError as exc:
                raise ValueError("invalid coordinate") from exc
        if name == "pos" and len(parts) == 2:
            result = self.map_service.get_object_position(self.scene, parts[1])
            return result or {"error": "not found", "object_id": parts[1]}
        if name == "walls" and len(parts) == 5:
            try:
                return self.map_service.get_walls_between(
                    self.scene,
                    (float(parts[1]), float(parts[2])),
                    (float(parts[3]), float(parts[4])),
                )
            except ValueError as exc:
                raise ValueError("invalid coordinate") from exc
        if name == "help":
            return {
                "commands": [
                    "area <x> <y>",
                    "pos <object_id>",
                    "walls <x1> <y1> <x2> <y2>",
                    "help",
                    "clear",
                ]
            }
        raise ValueError("unknown command. use: area <x> <y> | pos <object_id> | walls <x1> <y1> <x2> <y2> | help")

    def send_json(self, payload: dict, *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    main()
