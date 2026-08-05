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

    if args.agent_sim:
        if args.preview:
            start_preview_server(args.preview_port, scene, control)
        run_agent_sim_tick(scene, args, preview_service, control)
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
    parser.add_argument("--ran-mvp", action="store_true", help="run the default three-agent RAN scenario")
    parser.add_argument(
        "--ran-mvp-mode",
        choices=["aggregate", "tick"],
        default="aggregate",
        help="RAN MVP mode: aggregate summary or per-tick simulation",
    )
    parser.add_argument("--agent-sim", action="store_true", help="run the LLM/template guided agent simulation")
    parser.add_argument(
        "--agent-mode",
        choices=["template", "auto"],
        default="template",
        help="agent plan source: template (deterministic) or auto (LLM guided)",
    )
    parser.add_argument(
        "--agents-config",
        default=None,
        help="path to an agent simulation definition JSON (configs/agents/*.json)",
    )
    parser.add_argument(
        "--agent-speed",
        type=float,
        default=0.5,
        help="agent movement distance in meters per tick",
    )
    parser.add_argument(
        "--agent-radius",
        type=float,
        default=0.5,
        help="agent collision radius in meters",
    )
    parser.add_argument("--llm-endpoint", default=None, help="OpenAI-compatible endpoint base URL for auto mode")
    parser.add_argument("--llm-api-key", default=None, help="API key for the LLM endpoint")
    parser.add_argument("--llm-model", default="gpt-4o-mini", help="LLM model name for auto mode")
    parser.add_argument("--llm-record", default=None, help="record LLM plans to this JSONL file")
    parser.add_argument("--llm-replay", default=None, help="replay LLM plans from this JSONL file (no LLM calls)")
    parser.add_argument(
        "--llm-same-building",
        action="store_true",
        help="restrict LLM destination catalog to the agent's current building",
    )
    return parser.parse_args()


def run_agent_sim_tick(
    scene,
    args: argparse.Namespace,
    preview_service: LivePreviewService,
    control: SimulationControl,
) -> None:
    """运行 Agent 子系统仿真:Agent 移动 + 网络意图 + RAN 处理。"""

    from simulation.agent import build_default_three_agent_definition, load_agent_simulation_definition
    from simulation.agent.planning import LlmAgentPlanProvider, TemplatePlanProvider
    from simulation.orchestrator import SimulationOrchestrator

    if args.agents_config:
        definition = load_agent_simulation_definition(args.agents_config)
    else:
        definition = build_default_three_agent_definition()
    print(
        f"agent_sim simulation_id={definition.simulation_id} "
        f"mode={args.agent_mode} agents={definition.agent_count}",
        flush=True,
    )
    if args.agent_mode == "auto":
        plan_provider = LlmAgentPlanProvider(
            endpoint=args.llm_endpoint,
            api_key=args.llm_api_key,
            model=args.llm_model,
            record_path=args.llm_record,
            replay_path=args.llm_replay,
        )
    else:
        plan_provider = TemplatePlanProvider(definition)

    orchestrator = SimulationOrchestrator(
        scene,
        agent_definition=definition,
        plan_provider=plan_provider,
        agent_radius=args.agent_radius,
        speed_m_per_tick=args.agent_speed,
        same_building_only=args.llm_same_building,
    )
    state = SimulationState(scene=scene)
    loop = SimulationLoop(
        state,
        clock=SimulationClock(tick_ms=args.tick_ms),
        preview_service=preview_service,
        control=control,
        orchestrator=orchestrator,
    )
    loop.run(args.ticks)


def run_ran_mvp_aggregate(scene, tick: int) -> None:
    engine = RanEngine(scene)
    result = engine.run_scenario(tick=1, max_ticks=max(5000, tick))
    for service_state in result.get("service_states", []):
        summary = service_state["result"]
        qos = summary["qos"]
        progress = service_state["progress"]
        print(
            "ran_mvp="
            f"agent_id={service_state['agent_id']} "
            f"service_id={service_state['service_instance_id']} "
            f"delivered={summary['delivered_bytes']} "
            f"undelivered={summary['failed_bytes']} "
            f"tick_throughput_mbps={qos['throughput_mbps']:.3f} "
            f"latency_ms={qos['latency_ms']:.3f} "
            f"remaining_ratio={progress['remaining_ratio']:.6f} "
            f"loss_rate={qos['packet_loss_rate']:.6f}",
            flush=True,
        )
    progress = result["progress"]
    print(
        "ran_mvp_total="
        f"agents={result['agent_count']} "
        f"delivered={progress['delivered_bytes']} "
        f"requested={progress['requested_bytes']} "
        f"dropped={progress['dropped_bytes']} "
        f"remaining_ratio={progress['remaining_ratio']:.6f}",
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
        ran_scenario=engine.build_scenario(),
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
