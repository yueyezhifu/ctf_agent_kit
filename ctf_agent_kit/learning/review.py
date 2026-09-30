"""知识点复盘生成（学习优化）。

一次解题结束后（无论成败），把结构化笔记 + 轨迹归档转化为复盘文档：
- 涉及的知识点与掌握度自评
- 关键转折点（哪一步卡住了、怎么突破的）
- 可复用模式（下次同类题的先验）
- 错题标记（未解出 → 进入题库回放队列）

复盘生成可由 LLM 钩子增强；无钩子时用模板规则生成。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..core.notes import Notebook


@dataclass
class ReviewReport:
    """一份复盘报告。"""

    challenge_id: str
    category: str
    solved: bool
    knowledge_points: List[str] = field(default_factory=list)
    turning_points: List[str] = field(default_factory=list)
    reusable_patterns: List[str] = field(default_factory=list)
    mistakes: List[str] = field(default_factory=list)
    next_review_at: float = 0.0   # 错题重练时间（间隔重复）
    created_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        def section(title: str, items: List[str]) -> List[str]:
            lines = [f"## {title}"]
            lines.extend(f"- {i}" for i in items) if items else lines.append("（无）")
            return lines + [""]

        lines = [
            f"# 复盘报告：{self.challenge_id}",
            f"- 类别: {self.category}",
            f"- 结果: {'✅ 解出' if self.solved else '❌ 未解出（已入错题库）'}",
            f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.created_at))}",
            "",
        ]
        lines += section("知识点", self.knowledge_points)
        lines += section("关键转折点", self.turning_points)
        lines += section("可复用模式", self.reusable_patterns)
        lines += section("失误与教训", self.mistakes)
        if not self.solved and self.next_review_at:
            lines.append(
                f"## 下次重练\n- 计划时间: "
                f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(self.next_review_at))}")
        return "\n".join(lines)


# LLM 复盘钩子：输入上下文文本，返回复盘字段字典
ReviewHook = Callable[[str], dict]

# 类别 → 常见知识点候选（规则兜底）
CATEGORY_KNOWLEDGE = {
    "crypto": ["RSA 参数攻击", "分组模式误用", "古典密码", "随机数预测"],
    "reverse": ["静态反编译", "脱壳", "动态调试", "约束求解"],
    "pwn": ["栈溢出", "ROP 链构造", "堆利用", "格式化字符串"],
    "web": ["SQL 注入", "文件包含/上传", "反序列化", "逻辑越权"],
    "forensics": ["流量分析", "内存取证", "数据恢复", "时间线分析"],
    "misc": ["编码识别", "隐写术", "套娃剥离", "OSINT"],
}

# 间隔重复梯度（秒）：1天 → 3天 → 7天 → 14天
SPACED_INTERVALS = [86400, 3 * 86400, 7 * 86400, 14 * 86400]


class ReviewGenerator:
    """复盘报告生成器。"""

    def __init__(self, llm_hook: Optional[ReviewHook] = None) -> None:
        self.llm_hook = llm_hook

    def generate(self, challenge_id: str, category: str, solved: bool,
                 notebook: Notebook, prior_failures: int = 0) -> ReviewReport:
        """从解题笔记生成复盘。"""
        if self.llm_hook is not None:
            fields = self.llm_hook(notebook.render())
            return ReviewReport(challenge_id=challenge_id, category=category,
                                solved=solved, **fields)

        # 规则兜底：从笔记提炼
        failed_attempts = [a for a in notebook.attempts if a.result == "failed"]
        report = ReviewReport(
            challenge_id=challenge_id,
            category=category,
            solved=solved,
            knowledge_points=list(CATEGORY_KNOWLEDGE.get(category, [])),
            turning_points=[
                f"[{a.result}] {a.action}" for a in notebook.attempts
                if a.result == "success"
            ],
            reusable_patterns=[
                f.content for f in notebook.facts[:5]
            ],
            mistakes=[
                f"失败路径: {a.action} — {a.note}" for a in failed_attempts[:5]
            ],
        )
        if not solved:
            idx = min(prior_failures, len(SPACED_INTERVALS) - 1)
            report.next_review_at = time.time() + SPACED_INTERVALS[idx]
        return report
