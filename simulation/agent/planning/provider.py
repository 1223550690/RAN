"""Plan provider interface: decides "where to go and what to do".

Implementation conventions:
- request_plan returns a semantic plan (no coordinates); coordinate validity is enforced by the navigation layer.
- Returning None means the agent has no more plans (template exhausted or LLM end signal).
"""

from __future__ import annotations

from typing import Protocol

from ..contracts import AgentPlan


class AgentPlanProvider(Protocol):
    """Agent plan source: template or LLM."""

    def request_plan(self, agent_id: str, context: dict) -> AgentPlan | None:
        """Request the next plan for the given agent.

        context: read-only context provided by the caller (e.g. current tick, completed intent count),
        used by the implementation to decide termination or looping policy.
        """
        ...
