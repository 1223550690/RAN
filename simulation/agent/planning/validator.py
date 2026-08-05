"""计划校验:验证语义目标能否被导航层解析。

- 解析失败时返回错误信息,由上层决定重试或降级(重试 1 次后使用模板默认目标)。
- 只读,不修改任何状态。
"""

from __future__ import annotations

from ..contracts import AgentPlan
from ..navigation import NavigationPlanner


def validate_plan(plan: AgentPlan, navigation: NavigationPlanner) -> tuple[bool, str | None]:
    """校验计划的目标引用可解析;返回 (是否有效, 错误信息)。"""

    destination = navigation.resolve_destination(plan.destination_ref)
    if destination is None:
        return False, f"destination_ref unresolved: {plan.destination_ref!r}"
    if plan.intent_type not in ("video_call", "video_upload", "video_download", "file_transfer", "message"):
        return False, f"unknown intent_type: {plan.intent_type!r}"
    return True, None
