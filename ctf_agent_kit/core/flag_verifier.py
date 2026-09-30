"""flag 验证器（P0）。

- flag 格式正则配置化：支持多套格式（如 flag{...} / HTB{...} / 题目自定义），
  按题目或全局配置加载。
- 提交循环：允许多次提交，成功即终止（success terminates episode）。
- 验证优先走题目提供的远端校验接口（回调），无远端时用正则+精确比对兜底。

对应优化方案 P0-1：flag 验证器 + give_up 工具（NYU baseline 标配）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Pattern, Tuple


# 常见 flag 格式正则（按竞赛/平台扩展）
DEFAULT_FLAG_PATTERNS: List[str] = [
    r"flag\{[^\{\}\s]{1,128}\}",
    r"FLAG\{[^\{\}\s]{1,128}\}",
    r"HTB\{[^\{\}\s]{1,128}\}",
    r"CTF\{[^\{\}\s]{1,128}\}",
    r"cyberpeace\{[^\{\}\s]{1,128}\}",
    r"NSSCTF\{[^\{\}\s]{1,128}\}",
    r"[A-Za-z0-9_]{2,16}\{[A-Za-z0-9_\-!@#$%^&*+=:,.?]{1,128}\}",
]


@dataclass
class FlagFormatConfig:
    """一道题的 flag 格式配置。"""

    patterns: List[str] = field(default_factory=lambda: list(DEFAULT_FLAG_PATTERNS))
    exact_flag: Optional[str] = None  # 本地评测时可直接给定标准答案

    @classmethod
    def from_json(cls, path: str) -> "FlagFormatConfig":
        """从题目 metadata 的 JSON 配置加载 flag 格式。

        配置示例::

            {"flag_patterns": ["XYZCTF\\\\{[^}]+\\\\}"], "flag": "XYZCTF{demo}"}
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        patterns = data.get("flag_patterns") or list(DEFAULT_FLAG_PATTERNS)
        return cls(patterns=patterns, exact_flag=data.get("flag"))


@dataclass
class SubmissionResult:
    """单次提交结果。"""

    candidate: str
    accepted: bool
    source: str  # "remote" / "exact" / "pattern_only"
    detail: str = ""


class FlagVerifier:
    """flag 提取与提交验证循环。"""

    def __init__(
        self,
        config: Optional[FlagFormatConfig] = None,
        remote_checker: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.config = config or FlagFormatConfig()
        self.remote_checker = remote_checker
        self._compiled: List[Pattern[str]] = [
            re.compile(p) for p in self.config.patterns
        ]
        self.history: List[SubmissionResult] = []
        self.solved_flag: Optional[str] = None

    # -- 提取 ---------------------------------------------------------------

    def extract_candidates(self, text: str) -> List[str]:
        """从任意工具输出 / LLM 文本中按格式提取疑似 flag（去重保序）。"""
        found: List[str] = []
        seen = set()
        for pat in self._compiled:
            for m in pat.finditer(text):
                cand = m.group(0)
                if cand not in seen:
                    seen.add(cand)
                    found.append(cand)
        return found

    # -- 验证 ---------------------------------------------------------------

    def submit(self, candidate: str) -> SubmissionResult:
        """提交一个候选 flag。

        验证优先级：远端校验接口 > 本地精确比对 > 仅格式匹配（弱证据）。
        """
        if self.remote_checker is not None:
            ok = bool(self.remote_checker(candidate))
            result = SubmissionResult(candidate, ok, "remote")
        elif self.config.exact_flag is not None:
            ok = candidate.strip() == self.config.exact_flag.strip()
            result = SubmissionResult(candidate, ok, "exact")
        else:
            ok = any(p.fullmatch(candidate) for p in self._compiled)
            result = SubmissionResult(
                candidate, ok, "pattern_only",
                detail="无远端/标准答案，仅格式匹配，需 Validator 复核",
            )
        self.history.append(result)
        if result.accepted and result.source in ("remote", "exact"):
            self.solved_flag = candidate  # 成功即终止：记录并锁定
        return result

    def scan_and_submit(self, text: str) -> Tuple[bool, List[SubmissionResult]]:
        """从文本提取全部候选并依次提交；任一被接受即短路返回。"""
        results: List[SubmissionResult] = []
        for cand in self.extract_candidates(text):
            r = self.submit(cand)
            results.append(r)
            if r.accepted and r.source in ("remote", "exact"):
                return True, results
        return bool(self.solved_flag), results

    # -- 状态 ---------------------------------------------------------------

    @property
    def terminated(self) -> bool:
        """成功即终止：已有被确认的 flag。"""
        return self.solved_flag is not None

    def attempts(self) -> int:
        return len(self.history)

    def summary(self) -> str:
        lines = [f"提交次数: {len(self.history)}"]
        if self.solved_flag:
            lines.append(f"已确认 flag: {self.solved_flag}")
        for i, r in enumerate(self.history, 1):
            mark = "✓" if r.accepted else "✗"
            lines.append(f"  [{i}] {mark} {r.candidate} ({r.source})")
        return "\n".join(lines)
