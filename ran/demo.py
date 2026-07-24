from __future__ import annotations

import argparse
import json
import sys
sys.path.insert(1, '/home/tr22068/Documents/RAN/')

from services.scene_service import SceneService
from engine import RanEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RAN MVP upload scenario.")
    parser.add_argument("-s", "--scene", default="bristol_topology", help="registered scene name")
    parser.add_argument("--tick", type=int, default=1, help="simulation tick")
    parser.add_argument("--max-ticks", type=int, default=5000, help="maximum RAN ticks for the upload")
    parser.add_argument("--mode", choices=["aggregate", "tick"], default="aggregate", help="aggregate summary or per-tick states")
    args = parser.parse_args()

    scene = SceneService().load_scene(args.scene)
    engine = RanEngine(scene)
    if args.mode == "aggregate":
        results = engine.run_agent_upload_demo(tick=args.tick, max_ticks=args.max_ticks)
        for result in results:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    scenario = engine.build_upload_scenario()
    for offset in range(max(1, args.max_ticks)):
        states = scenario.step(args.tick + offset)
        for state in states:
            print(json.dumps(state, ensure_ascii=False))
        if state.get("status") == "completed":
            break

#MAKE NEW SCENARIO, MULTIPLE UPLOAD AND MULTIPLE DOWNLOAD FOR SCHEDULING TESTS
if __name__ == "__main__":
    main()
