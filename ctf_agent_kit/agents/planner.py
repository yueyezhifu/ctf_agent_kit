"""Planner —— 全局计划制定与动态修订（P1，D-CIPHER 三角色之一）。

职责：
- 维护全局解题计划（一组有序 Task）。
- 根据 Executor 回传的摘要动态修订计划（标记完成/失败、插入新任务、
  调整优先级），而不是每次从头再来（HPTSA team manager 模式）。
- 失败重派：任务失败时，由 AutoPrompter 生成更详细指令后重新入队。
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import List, Optional


_task_id_counter = itertools.count(1)


@dataclass
class Task:
    """计划中的一个子任务。"""

    description: str
    task_id: int = field(default_factory=lambda: next(_task_id_counter))
    status: str = "pending"  # pending / in_progress / done / failed
    instruction: str = ""     # AutoPrompter 生成的详细执行指令
    retry_of: Optional[int] = None
    attempts: int = 0
    result_summary: str = ""

    MAX_ATTEMPTS: int = 3

    def can_retry(self) -> bool:
        return self.attempts < self.MAX_ATTEMPTS


class Planner:
    """全局计划维护者。

    LLM 交互由上层注入（plan_llm 回调），本类负责计划数据结构与修订逻辑。
    """

    def __init__(self, challenge_description: str = "") -> None:
        self.challenge_description = challenge_description
        self.tasks: List[Task] = []
        self.revision_log: List[str] = []

    # -- 计划建立 -----------------------------------------------------------

    def initialize(self, task_descriptions: List[str]) -> None:
        """由 LLM 首轮输出初始化计划。"""
        self.tasks = [Task(description=d) for d in task_descriptions]
        self.revision_log.append(f"[{time.strftime('%H:%M:%S')}] 初始化计划，{len(self.tasks)} 个任务")

    # -- 计划修订 -----------------------------------------------------------

    def next_task(self) -> Optional[Task]:
        """取下一个待执行任务。"""
        for t in self.tasks:
            if t.status == "pending":
                t.status = "in_progress"
                t.attempts += 1
                return t
        return None

    def report_success(self, task_id: int, summary: str) -> None:
        t = self._get(task_id)
        t.status = "done"
        t.result_summary = summary
        self.revision_log.append(f"任务 #{task_id} 完成: {summary[:120]}")

    def report_failure(self, task_id: int, summary: str, refined_instruction: str = "") -> Optional[Task]:
        """任务失败处理：带更详细指令重派（HPTSA），而非从头再来。

        返回重派的新任务；超过重试上限则返回 None。
        """
        t = self._get(task_id)
        t.result_summary = summary
        self.revision_log.append(f"任务 #{task_id} 失败(第{t.attempts}次): {summary[:120]}")
        if not t.can_retry():
            t.status = "failed"
            self.revision_log.append(f"任务 #{task_id} 已达重试上限，标记失败")
            return None
        retry = Task(
            description=t.description,
            instruction=refined_instruction or t.instruction,
            retry_of=t.task_id,
        )
        # 插入到当前位置之后，保持计划顺序
        idx = self.tasks.index(t)
        self.tasks.insert(idx + 1, retry)
        t.status = "failed"
        self.revision_log.append(f"任务 #{task_id} 重派为 #{retry.task_id}（带细化指令）")
        return retry

    def insert_tasks(self, descriptions: List[str], after_task_id: Optional[int] = None) -> None:
        """动态插入新任务（Executor 发现新攻击面时由 Planner 增补计划）。"""
        new_tasks = [Task(description=d) for d in descriptions]
        if after_task_id is None:
            self.tasks.extend(new_tasks)
        else:
            idx = self.tasks.index(self._get(after_task_id))
            for offset, t in enumerate(new_tasks, 1):
                self.tasks.insert(idx + offset, t)
        self.revision_log.append(f"插入 {len(new_tasks)} 个新任务")

    # -- 视图 ---------------------------------------------------------------

    def is_exhausted(self) -> bool:
        """无待执行任务（全部完成或失败）。"""
        return all(t.status in ("done", "failed") for t in self.tasks)

    def render_plan(self) -> str:
        icons = {"pending": "⬜", "in_progress": "🔄", "done": "✅", "failed": "❌"}
        lines = ["# 全局计划"]
        for t in self.tasks:
            suffix = f"（重派自 #{t.retry_of}）" if t.retry_of else ""
            lines.append(f"- {icons[t.status]} #{t.task_id} {t.description}{suffix}")
        return "\n".join(lines)

    def _get(self, task_id: int) -> Task:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        raise KeyError(f"任务 #{task_id} 不存在")
