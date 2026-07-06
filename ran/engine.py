from __future__ import annotations

from ran.scheduler import JavaSchedulerAdapter
from ran.scenario import RanUploadScenario


class RanEngine:
    """RAN MVP 编排器。

    输入:
    - scene: 当前地图拓扑。
    - scheduler: 可替换 scheduler，默认使用 JavaSchedulerAdapter 的 Python fallback。

    输出:
    - EndToEndResult 与每层调试记录。
    """

    def __init__(self, scene, scheduler=None) -> None:
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()

    def run_agent_upload_demo(self, *, tick: int = 1, max_ticks: int = 5000) -> dict[str, object]:
        """执行固定测试背景。

        测试背景:
        - Agent 在学生活动中心入口大厅附近。
        - 手机通过 5G 上传 100MB 视频到 youtube_server。

        输出:
        - 包含 EndToEndResult 和各层关键对象的 dict，便于 CLI/预览展示。
        """

        scenario = RanUploadScenario(self.scene, scheduler=self.scheduler)
        state: dict[str, object] | None = None
        for offset in range(max(1, max_ticks)):
            state = scenario.step(tick + offset)
            if state.get("status") == "completed":
                break
        if state is None:
            raise RuntimeError("RAN MVP aggregate mode did not execute")
        state["mode"] = "aggregate"
        return state

    def build_upload_scenario(self) -> RanUploadScenario:
        """创建可逐 tick 推进的上传场景。"""

        return RanUploadScenario(self.scene, scheduler=self.scheduler)
