from __future__ import annotations

from typing import Protocol

from ran.contracts import SchedulerRequest, SchedulerResult


class Scheduler(Protocol):
    """MAC Scheduler 接口。

    输入:
    - SchedulerRequest。

    输出:
    - SchedulerResult。
    """

    def allocate(self, request: SchedulerRequest) -> SchedulerResult:
        """执行一次 PRB/MCS 分配。"""
        ...
