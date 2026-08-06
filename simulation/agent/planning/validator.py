"""Plan validation: verifies the semantic destination can be resolved by the navigation layer.

- On resolution failure, returns the error message; the caller decides to retry or degrade (after 1 retry, fall back to the template default destination).
- Read-only; does not modify any state.
"""

from __future__ import annotations

from ..contracts import AgentPlan
from ..navigation import NavigationPlanner


def validate_plan(plan: AgentPlan, navigation: NavigationPlanner) -> tuple[bool, str | None]:
    """Validate that the plan's destination reference resolves; returns (valid, error message)."""

    destination = navigation.resolve_destination(plan.destination_ref)
    if destination is None:
        return False, f"destination_ref unresolved: {plan.destination_ref!r}"
    if plan.intent_type not in ("video_call", "video_upload", "video_download", "file_transfer", "message"):
        return False, f"unknown intent_type: {plan.intent_type!r}"
    return True, None
