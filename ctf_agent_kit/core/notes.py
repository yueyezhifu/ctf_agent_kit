"""结构化笔记机制（P0）。

对应优化方案 P0-3：每轮让 LLM 更新一份「已知事实 / 已尝试路径 / 下一步候选」
的结构化笔记，替代无限膨胀的完整历史（hackingBuddyGPT update-state 模式）；
长输出用 LM 摘要钩子压缩，而非硬截断（EnIGMA Summarizer，+2.6pt）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional


# LM 摘要钩子签名：输入超长文本，返回压缩后的摘要
SummarizerHook = Callable[[str], str]


@dataclass
class Fact:
    """一条已知事实，必须绑定证据来源（配合幻觉防护）。"""

    content: str
    evidence: str = ""  # 产生该结论的工具输出摘录 / 会话 ID
    added_at: float = field(default_factory=time.time)


@dataclass
class AttemptedPath:
    """一条已尝试路径及其结果，避免重复尝试。"""

    action: str
    result: str  # "success" / "failed" / "inconclusive"
    note: str = ""
    added_at: float = field(default_factory=time.time)


class Notebook:
    """跨轮持久的状态笔记，是 agent 唯一的工作记忆。

    LLM 每轮输出对笔记的增量更新（add_fact / add_attempt / set_candidates），
    而不是把全部历史塞进上下文。
    """

    MAX_FACTS = 200
    MAX_ATTEMPTS = 200
    MAX_FIELD_CHARS = 4_000  # 单字段超过此长度时走 LM 摘要钩子

    def __init__(self, challenge_id: str = "", summarizer: Optional[SummarizerHook] = None) -> None:
        self.challenge_id = challenge_id
        self.facts: List[Fact] = []
        self.attempts: List[AttemptedPath] = []
        self.next_candidates: List[str] = []
        self.summarizer = summarizer  # LM 摘要钩子（未注入时退化为智能截断）

    # -- 更新 ---------------------------------------------------------------

    def add_fact(self, content: str, evidence: str = "") -> None:
        self.facts.append(Fact(self._compress(content), self._compress(evidence)))
        if len(self.facts) > self.MAX_FACTS:
            self.facts = self.facts[-self.MAX_FACTS:]

    def add_attempt(self, action: str, result: str, note: str = "") -> None:
        self.attempts.append(
            AttemptedPath(self._compress(action), result, self._compress(note))
        )
        if len(self.attempts) > self.MAX_ATTEMPTS:
            self.attempts = self.attempts[-self.MAX_ATTEMPTS:]

    def set_candidates(self, candidates: List[str]) -> None:
        """整体替换下一步候选列表（由 Planner/LLM 每轮刷新）。"""
        self.next_candidates = [self._compress(c) for c in candidates]

    def already_tried(self, action_substr: str) -> bool:
        """查重：某类动作是否已尝试过，避免循环撞墙。"""
        return any(action_substr in a.action for a in self.attempts)

    # -- 压缩 ---------------------------------------------------------------

    def _compress(self, text: str) -> str:
        """长文本压缩：优先 LM 摘要钩子，未配置时智能截断（保留首尾）。"""
        if len(text) <= self.MAX_FIELD_CHARS:
            return text
        if self.summarizer is not None:
            return self.summarizer(text)
        half = self.MAX_FIELD_CHARS // 2
        return text[:half] + "\n...[截断]...\n" + text[-half:]

    # -- 渲染 ---------------------------------------------------------------

    def render(self) -> str:
        """渲染为注入 prompt 的 Markdown 笔记。"""
        lines = [f"# 解题笔记 ({self.challenge_id or 'unknown'})", ""]
        lines.append("## 已知事实")
        if self.facts:
            for i, f in enumerate(self.facts, 1):
                ev = f"（证据: {f.evidence[:200]}）" if f.evidence else ""
                lines.append(f"{i}. {f.content}{ev}")
        else:
            lines.append("（暂无）")
        lines.append("")
        lines.append("## 已尝试路径")
        if self.attempts:
            for a in self.attempts:
                lines.append(f"- [{a.result}] {a.action} — {a.note}")
        else:
            lines.append("（暂无）")
        lines.append("")
        lines.append("## 下一步候选")
        if self.next_candidates:
            for c in self.next_candidates:
                lines.append(f"- {c}")
        else:
            lines.append("（暂无）")
        return "\n".join(lines)
