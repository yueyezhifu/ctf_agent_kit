"""多轨迹并行采样（P2，对标 Naptime / Cybench pass@k）。

同题并行跑 N 条相互独立的解题轨迹（独立笔记、独立会话、独立预算），
任一轨迹拿到被验证的 flag 即判该题通过，统计 pass@k。
骨架：线程池并发 + 轨迹回调注入，真实 LLM 驱动由上层提供。
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .budget import Budget
from .flag_verifier import FlagVerifier
from .notes import Notebook


@dataclass
class TrajectoryResult:
    """单条轨迹的结局。"""

    trajectory_id: int
    solved: bool
    flag: Optional[str] = None
    rounds: int = 0
    cost_usd: float = 0.0
    error: str = ""


@dataclass
class ParallelResult:
    """一道题的并行采样汇总。"""

    challenge_id: str
    k: int
    trajectories: List[TrajectoryResult] = field(default_factory=list)

    @property
    def pass_at_k(self) -> bool:
        return any(t.solved for t in self.trajectories)

    @property
    def total_cost(self) -> float:
        return sum(t.cost_usd for t in self.trajectories)

    @property
    def first_solve_rounds(self) -> Optional[int]:
        solved = [t.rounds for t in self.trajectories if t.solved]
        return min(solved) if solved else None


# 单条轨迹驱动签名：(轨迹ID, 笔记, 预算, flag验证器) → TrajectoryResult
TrajectoryRunner = Callable[[int, Notebook, Budget, FlagVerifier], TrajectoryResult]


class ParallelSampler:
    """同题 N 条独立轨迹的并行采样器。"""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    def sample(self, challenge_id: str, k: int,
               trajectory_runner: TrajectoryRunner,
               budget_factory: Callable[[], Budget],
               verifier_factory: Callable[[], FlagVerifier],
               early_stop: bool = True) -> ParallelResult:
        """并行跑 k 条轨迹。

        ``early_stop=True`` 时，任一轨迹确认解出即取消其余轨迹
        （节约 token，对应「成功多在早期」的经验）。
        每条轨迹使用独立的 Notebook / Budget / FlagVerifier 实例，互不污染。
        """
        result = ParallelResult(challenge_id=challenge_id, k=k)
        solved_event = threading.Event()

        def run_one(tid: int) -> TrajectoryResult:
            if early_stop and solved_event.is_set():
                return TrajectoryResult(tid, solved=False, error="cancelled: 其他轨迹已解出")
            r = trajectory_runner(
                tid, Notebook(challenge_id), budget_factory(), verifier_factory())
            if r.solved:
                solved_event.set()
            return r

        with ThreadPoolExecutor(max_workers=min(self.max_workers, k)) as pool:
            futures = [pool.submit(run_one, i) for i in range(k)]
            for fut in as_completed(futures):
                result.trajectories.append(fut.result())
        return result
