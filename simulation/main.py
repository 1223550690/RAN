from __future__ import annotations

import argparse
import functools
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agents.agent import AgentState
from agents.decision import AgentDecisionController
from agents.llm_client import DeepSeekClient
from agents.mobility import find_area_id
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
    agents = create_agents(scene)
    preview_service = LivePreviewService(PROJECT_ROOT / "outputs" / "live_state.json")
    decision_controller = create_decision_controller(args)

    if args.preview:
        start_preview_server(args.preview_port)

    state = SimulationState(scene=scene, agents=agents)
    loop = SimulationLoop(
        state,
        clock=SimulationClock(tick_ms=args.tick_ms),
        preview_service=preview_service,
        decision_controller=decision_controller,
        seed=args.seed,
    )
    loop.run(args.ticks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RAN behavior simulation loop.")
    parser.add_argument("-s", "--scene", default="potions_teacher_office", help="registered scene name")
    parser.add_argument("--ticks", type=int, default=200, help="number of ticks to run")
    parser.add_argument("--tick-ms", type=int, default=500, help="milliseconds per tick")
    parser.add_argument("--seed", type=int, default=7, help="random seed for simple mobility")
    parser.add_argument("--no-llm", action="store_true", help="disable LLM behavior decisions")
    parser.add_argument("--llm-model", default=None, help="DeepSeek model name")
    parser.add_argument("--llm-timeout", type=int, default=30, help="DeepSeek request timeout seconds")
    parser.add_argument("--llm-cooldown", type=float, default=30.0, help="seconds between LLM calls after behavior ends")
    parser.add_argument("-p", "--preview", action="store_true", help="open the live preview page")
    parser.add_argument("--preview-port", type=int, default=8765, help="preview server port")
    return parser.parse_args()


def create_decision_controller(args: argparse.Namespace) -> AgentDecisionController | None:
    if args.no_llm:
        print("llm=disabled", flush=True)
        return None

    client = DeepSeekClient.from_env(model=args.llm_model, timeout_seconds=args.llm_timeout)
    if not client.enabled:
        print("llm=disabled_missing_DEEPSEEK_API_KEY; using local fallback mobility", flush=True)
        return None

    print(f"llm=deepseek model={client.model} cooldown={args.llm_cooldown}s", flush=True)
    return AgentDecisionController(client, cooldown_seconds=args.llm_cooldown)


def create_agents(scene) -> list[AgentState]:
    start = scene.default_agent_start or first_area_center(scene)
    area_id = find_area_id(scene, start)
    return [
        AgentState(
            agent_id="agent_001",
            name="Alice",
            position=start,
            area_id=area_id,
            behavior="idle",
            color="#7f4ac9",
            speed=0.12,
        )
    ]


def first_area_center(scene) -> tuple[float, float]:
    area = scene.areas[0]
    min_x, min_y, max_x, max_y = area.bounds
    return ((min_x + max_x) / 2, (min_y + max_y) / 2)


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
