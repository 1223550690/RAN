from __future__ import annotations

from typing import Protocol

from ran.contracts import SchedulerRequest, SchedulerResult


class Scheduler(Protocol):
    """Project implementation detail."""

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """Project implementation detail."""
        ...
