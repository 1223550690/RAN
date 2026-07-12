from __future__ import annotations

from dataclasses import dataclass

from .common import Position


@dataclass(slots=True)
class AgentIntent:
    """Project implementation detail."""

    agent_id: str
    agent_pos: Position
    action: str
    target: str
    content_type: str
    size_bytes: int
