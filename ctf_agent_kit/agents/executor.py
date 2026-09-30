"""Executor —— 独立会话的子任务执行者（P1，D-CIPHER 三角色之一）。

职责：
- 在独立会话/上下文中执行 Planner 下发的单个子任务。
- 上下文隔离：执行过程的全部细节（冗长工具输出）不回流给 Planner，
  只回传结论摘要（D-CIPHER 关键设计，防止主上下文被淹没）。
- 内部同样受预算与幻觉防护约束。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..core.budget import Budget, BudgetExceeded, GiveUp
from ..core.guardrails import Guardrails
from ..core.notes import Notebook


@dataclass
class ExecutionResult:
    """回传给 Planner 的摘要（唯一出口）。"""

    success: bool
    summary: str                    # 给 Planner 的简短结论
    findings: List[str] = field(default_factory=list)  # 新发现（供 Planner 增补计划）
    flag_candidate: Optional[str] = None
    rounds_used: int = 0
    failure_detail: str = ""        # 失败时的详细现场，供 AutoPrompter 细化重派指令


# 工具执行器签名：工具名 + 参数 → 输出文本
ToolRunner = Callable[[str, str], str]


class Executor:
    """子任务执行会话。"""

    def __init__(
        self,
        tool_runner: Optional[ToolRunner] = None,
        budget: Optional[Budget] = None,
        guardrails: Optional[Guardrails] = None,
    ) -> None:
        self.tool_runner = tool_runner or self._default_tool_runner
        self.budget = budget or Budget.for_category("misc")
        self.guardrails = guardrails or Guardrails()
        self.notes = Notebook()

    def run(self, task_description: str, instruction: str = "",
            llm_step: Optional[Callable[[str], dict]] = None) -> ExecutionResult:
        """执行一个子任务。

        ``llm_step`` 回调签名：输入当前 prompt 上下文，返回
        ``{"tool": 名称, "args": 参数, "thought": 思考, "final": 是否收束}``。
        未注入 LLM 时仅做骨架演练（直接返回未执行结果）。
        """
        if llm_step is None:
            return ExecutionResult(
                success=False,
                summary="未注入 LLM 驱动，Executor 骨架待命",
                failure_detail="no llm_step provided",
            )

        context = (
            f"子任务: {task_description}\n"
            f"详细指令: {instruction or '(无)'}\n"
            f"{self.notes.render()}\n"
        )
        while True:
            try:
                self.budget.check()
            except BudgetExceeded as e:
                return ExecutionResult(
                    success=False, summary=f"预算耗尽: {e.reason}",
                    rounds_used=self.budget.rounds_used, failure_detail=str(e),
                )

            step = llm_step(context)
            thought = step.get("thought", "")

            # 幻觉防护：检查本轮
            had_tool = bool(step.get("tool"))
            report = self.guardrails.check_round(thought, had_tool)
            if not report.ok:
                context += "\n" + report.corrective_prompt

            if step.get("final"):
                summary = step.get("summary", thought[:300])
                return ExecutionResult(
                    success=bool(step.get("success")),
                    summary=summary,
                    findings=list(step.get("findings") or []),
                    flag_candidate=step.get("flag_candidate"),
                    rounds_used=self.budget.rounds_used,
                    failure_detail="" if step.get("success") else summary,
                )

            if had_tool:
                call_id = f"call-{self.budget.rounds_used + 1}"
                self.guardrails.register_tool_call(call_id)
                output = self.tool_runner(step["tool"], step.get("args", ""))
                self.notes.add_fact(
                    f"工具 {step['tool']} 输出要点", evidence=output[:500]
                )
                context += f"\n[工具 {step['tool']} 输出]\n{output[:2000]}\n"

            try:
                self.budget.record_round()
            except BudgetExceeded:
                pass  # 下轮循环开头统一处理

    @staticmethod
    def _default_tool_runner(tool: str, args: str) -> str:
        return f"[stub] 工具 {tool} 未接入真实执行器，参数: {args[:100]}"
