"""基准评测骨架（P2）：NYU CTF Bench / Cybench。

- 加载基准题目清单（JSONL：id/category/描述/附件路径/标准 flag）。
- 逐题跑解题轨迹（可接 ParallelSampler 做 pass@k）。
- 报告 pass@1 / pass@5、按类别分解、成本统计；按类别预算上限截断长尾。
- 结果落盘 JSON，支持回归对比。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..core.budget import Budget, CATEGORY_BUDGETS
from ..core.parallel import ParallelResult, ParallelSampler, TrajectoryResult

SUPPORTED_BENCHMARKS = ("nyu_ctf_bench", "cybench")


@dataclass
class BenchTask:
    """基准中的一道题。"""

    challenge_id: str
    category: str
    description: str
    flag: str
    attachments_dir: str = ""
    subtasks: List[str] = field(default_factory=list)  # Cybench 子任务分解


@dataclass
class TaskOutcome:
    challenge_id: str
    category: str
    solved_pass1: bool
    solved_passk: bool
    rounds: int
    cost_usd: float
    seconds: float
    k: int
    error: str = ""


@dataclass
class BenchReport:
    benchmark: str
    total: int
    pass_at_1: float
    pass_at_5: float
    total_cost_usd: float
    total_seconds: float
    by_category: Dict[str, Dict[str, float]] = field(default_factory=dict)
    outcomes: List[Dict] = field(default_factory=list)


# 解题驱动签名：(task, k, budget) → ParallelResult
SolveDriver = Callable[[BenchTask, int, Budget], ParallelResult]


class BenchRunner:
    """评测运行器。"""

    def __init__(self, benchmark: str, tasks_path: str,
                 budget_overrides: Optional[Dict[str, Dict]] = None) -> None:
        if benchmark not in SUPPORTED_BENCHMARKS:
            raise ValueError(f"未知基准 {benchmark!r}，支持: {SUPPORTED_BENCHMARKS}")
        self.benchmark = benchmark
        self.tasks = self._load_tasks(tasks_path)
        self.budget_overrides = budget_overrides or {}
        self.sampler = ParallelSampler(max_workers=4)

    @staticmethod
    def _load_tasks(path: str) -> List[BenchTask]:
        tasks: List[BenchTask] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                tasks.append(BenchTask(**json.loads(line)))
        return tasks

    def run(self, solve_driver: SolveDriver, k: int = 5,
            categories: Optional[List[str]] = None,
            limit: Optional[int] = None) -> BenchReport:
        """跑全量（或按类别/数量子集）评测。

        ``k``：每题采样轨迹数 → pass@k；pass@1 取第一条轨迹结果。
        """
        outcomes: List[TaskOutcome] = []
        tasks = [t for t in self.tasks
                 if categories is None or t.category in categories]
        if limit:
            tasks = tasks[:limit]

        for task in tasks:
            budget = self._budget_for(task.category)
            started = time.monotonic()
            try:
                result = solve_driver(task, k, budget)
                outcomes.append(TaskOutcome(
                    challenge_id=task.challenge_id,
                    category=task.category,
                    solved_pass1=bool(result.trajectories and
                                      result.trajectories[0].solved),
                    solved_passk=result.pass_at_k,
                    rounds=result.first_solve_rounds or 0,
                    cost_usd=result.total_cost,
                    seconds=time.monotonic() - started,
                    k=k,
                ))
            except Exception as e:  # 单题崩溃不拖垮整轮评测
                outcomes.append(TaskOutcome(
                    challenge_id=task.challenge_id, category=task.category,
                    solved_pass1=False, solved_passk=False, rounds=0,
                    cost_usd=0.0, seconds=time.monotonic() - started,
                    k=k, error=f"{type(e).__name__}: {e}"))
        return self._report(outcomes, k)

    # -- 预算 -----------------------------------------------------------------

    def _budget_for(self, category: str) -> Budget:
        """按类别预算上限（方案 P2-12：成功多在早期，长尾纯烧钱）。"""
        overrides = dict(CATEGORY_BUDGETS.get(category, CATEGORY_BUDGETS["misc"]))
        overrides.update(self.budget_overrides.get(category, {}))
        return Budget(category=category, **overrides)

    # -- 报告 -----------------------------------------------------------------

    def _report(self, outcomes: List[TaskOutcome], k: int) -> BenchReport:
        total = len(outcomes)
        p1 = sum(o.solved_pass1 for o in outcomes) / total if total else 0.0
        pk = sum(o.solved_passk for o in outcomes) / total if total else 0.0

        by_cat: Dict[str, Dict[str, float]] = {}
        cats = sorted({o.category for o in outcomes})
        for c in cats:
            sub = [o for o in outcomes if o.category == c]
            n = len(sub)
            by_cat[c] = {
                "total": n,
                "pass_at_1": round(sum(o.solved_pass1 for o in sub) / n, 4),
                f"pass_at_{k}": round(sum(o.solved_passk for o in sub) / n, 4),
                "avg_cost_usd": round(sum(o.cost_usd for o in sub) / n, 4),
            }

        return BenchReport(
            benchmark=self.benchmark,
            total=total,
            pass_at_1=round(p1, 4),
            pass_at_5=round(pk, 4) if k == 5 else round(pk, 4),
            total_cost_usd=round(sum(o.cost_usd for o in outcomes), 4),
            total_seconds=round(sum(o.seconds for o in outcomes), 1),
            by_category=by_cat,
            outcomes=[asdict(o) for o in outcomes],
        )

    @staticmethod
    def save_report(report: BenchReport, path: str) -> None:
        Path(path).write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2),
            encoding="utf-8")
