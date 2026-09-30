"""预算与强制退出控制（P0）。

对应优化方案 P0-1 后半：设置成本/轮次上限（exit_cost），
超限或智能体主动 give_up 时强制终止 episode，防止长尾纯烧钱。

同时支撑 P2-12：按类别设预算上限（成功多在早期）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


class BudgetExceeded(Exception):
    """预算超限，episode 必须终止。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class GiveUp(Exception):
    """智能体主动放弃（give_up 工具），强制退出。"""

    def __init__(self, reason: str = "") -> None:
        super().__init__(reason or "agent gave up")
        self.reason = reason or "agent gave up"


# 按题类别推荐的默认预算（经验值：多数成功发生在早期轮次）
CATEGORY_BUDGETS: Dict[str, Dict[str, float]] = {
    "crypto":    {"max_rounds": 30, "max_tokens": 300_000, "max_cost_usd": 2.0, "max_seconds": 1800},
    "reverse":   {"max_rounds": 40, "max_tokens": 400_000, "max_cost_usd": 3.0, "max_seconds": 2400},
    "pwn":       {"max_rounds": 60, "max_tokens": 600_000, "max_cost_usd": 5.0, "max_seconds": 3600},
    "web":       {"max_rounds": 40, "max_tokens": 400_000, "max_cost_usd": 3.0, "max_seconds": 2400},
    "forensics": {"max_rounds": 30, "max_tokens": 300_000, "max_cost_usd": 2.0, "max_seconds": 1800},
    "misc":      {"max_rounds": 30, "max_tokens": 300_000, "max_cost_usd": 2.0, "max_seconds": 1800},
}


@dataclass
class Budget:
    """单题 episode 预算。"""

    category: str = "misc"
    max_rounds: int = 30
    max_tokens: int = 300_000
    max_cost_usd: float = 2.0
    max_seconds: float = 1800.0

    rounds_used: int = 0
    tokens_used: int = 0
    cost_used: float = 0.0
    started_at: float = field(default_factory=time.monotonic)

    @classmethod
    def for_category(cls, category: str, **overrides) -> "Budget":
        """按类别取推荐预算，可用关键字参数覆盖。"""
        defaults = dict(CATEGORY_BUDGETS.get(category, CATEGORY_BUDGETS["misc"]))
        defaults.update(overrides)
        return cls(category=category, **defaults)

    # -- 计量 ---------------------------------------------------------------

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def record_round(self, tokens: int = 0, cost_usd: float = 0.0) -> None:
        """记录一轮消耗并检查是否超限。"""
        self.rounds_used += 1
        self.tokens_used += tokens
        self.cost_used += cost_usd
        self.check()

    def check(self) -> None:
        """任一维度超限即抛 BudgetExceeded。"""
        if self.rounds_used >= self.max_rounds:
            raise BudgetExceeded(
                f"轮次超限: {self.rounds_used}/{self.max_rounds} (类别 {self.category})"
            )
        if self.tokens_used >= self.max_tokens:
            raise BudgetExceeded(
                f"token 超限: {self.tokens_used}/{self.max_tokens}"
            )
        if self.cost_used >= self.max_cost_usd:
            raise BudgetExceeded(
                f"成本超限: ${self.cost_used:.4f}/${self.max_cost_usd}"
            )
        if self.elapsed >= self.max_seconds:
            raise BudgetExceeded(
                f"时间超限: {self.elapsed:.0f}s/{self.max_seconds:.0f}s"
            )

    def give_up(self, reason: str = "") -> None:
        """give_up 工具入口：智能体判断无解时主动终止。"""
        raise GiveUp(reason)

    # -- 报告 ---------------------------------------------------------------

    def remaining(self) -> Dict[str, float]:
        return {
            "rounds": self.max_rounds - self.rounds_used,
            "tokens": self.max_tokens - self.tokens_used,
            "cost_usd": round(self.max_cost_usd - self.cost_used, 4),
            "seconds": round(self.max_seconds - self.elapsed, 1),
        }

    def report(self) -> str:
        return (
            f"[预算] 类别={self.category} "
            f"轮次 {self.rounds_used}/{self.max_rounds} | "
            f"tokens {self.tokens_used}/{self.max_tokens} | "
            f"成本 ${self.cost_used:.4f}/${self.max_cost_usd} | "
            f"用时 {self.elapsed:.0f}s/{self.max_seconds:.0f}s"
        )
