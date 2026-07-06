"""RAN MVP package.

本包提供从 Agent 意图到 Data Network 的最小 5G RAN/5GC 仿真链路。
当前实现重点是稳定输入输出接口，协议、信道、调度、核心网转发逻辑均为
MVP 简化版本，后续可由组员逐层替换内部算法。
"""

from .engine import RanEngine

__all__ = ["RanEngine"]
