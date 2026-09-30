"""AutoPrompter —— 任务指令精化器（P1，D-CIPHER 三角色之一）。

职责：
- 把 Planner 的一句话任务描述展开成 Executor 可直接执行的详细指令。
- 任务失败时，结合失败现场生成「更详细、带纠偏」的重派指令，
  而不是简单重试（HPTSA team manager 模式）。
- 按题类别注入对应解题 playbook 与 few-shot demo 引用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..learning.classifier import classify


_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class AutoPrompter:
    """生成与精化 Executor 指令。"""

    def __init__(self, prompts_root: Optional[str] = None) -> None:
        self.prompts_root = Path(prompts_root) if prompts_root else _PACKAGE_ROOT

    def build_instruction(self, task_description: str, category: str = "",
                          challenge_description: str = "") -> str:
        """为新任务生成首次执行指令。"""
        category = category or classify(challenge_description or task_description)
        parts = [
            f"任务: {task_description}",
            f"题型类别: {category}",
            "",
            "执行要求:",
            "1. 每步操作必须通过工具执行，禁止凭空断言结果。",
            "2. 每条结论注明产生它的工具调用与输出摘录。",
            "3. 发现疑似 flag 立即调用 submit_flag 验证，格式匹配不算成功。",
            "4. 收束时返回 ≤200 字摘要 + 新发现列表。",
        ]
        demo_hint = self._demo_hint(category)
        if demo_hint:
            parts += ["", demo_hint]
        return "\n".join(parts)

    def refine_for_retry(self, task_description: str, failure_detail: str,
                         attempt: int, category: str = "") -> str:
        """失败重派：生成带纠偏的更详细指令。"""
        base = self.build_instruction(task_description, category)
        parts = [
            base,
            "",
            f"【第 {attempt} 次重派】上一次失败现场:",
            failure_detail[:1000],
            "",
            "纠偏要求:",
            "- 不要重复上次已失败的完全相同操作。",
            "- 先分析失败原因（工具报错？假设错误？参数不对？），再换路径。",
            "- 若同一思路已失败 2 次，必须切换到 playbook 中的备选攻击链。",
        ]
        return "\n".join(parts)

    def _demo_hint(self, category: str) -> str:
        """引用对应类别的 few-shot demo 与攻击 playbook（存在时）。"""
        demo = self.prompts_root / "prompts" / "demos" / f"{category}.md"
        playbook = self.prompts_root / "offense" / "playbooks" / f"{category}.md"
        hints = []
        if demo.exists():
            hints.append(f"参考解题演示: {demo}")
        if playbook.exists():
            hints.append(f"参考攻击 playbook: {playbook}")
        return "\n".join(hints)
