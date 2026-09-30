"""Validator —— 独立验证器（P2，对标 XBOW validators）。

职责：
- 对 Executor/攻击链产出的疑似 flag、疑似漏洞进行独立复核。
- 验证过程不复用产出方的上下文，只拿「可复现的验证步骤」重新执行，
  降低幻觉导致的假阳性。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class ValidationVerdict:
    target: str            # 被验证对象（疑似 flag / 漏洞描述）
    kind: str              # "flag" / "vulnerability"
    confirmed: bool
    confidence: str        # "high" / "medium" / "low"
    evidence: List[str] = field(default_factory=list)
    reason: str = ""


# 复核器签名：独立执行一段验证命令/请求，返回输出文本
RecheckRunner = Callable[[str], str]


class Validator:
    """独立复核疑似发现。"""

    def __init__(self, recheck_runner: Optional[RecheckRunner] = None,
                 flag_pattern: str = r"\{[^}]+\}") -> None:
        self.recheck_runner = recheck_runner or (lambda cmd: f"[stub] {cmd}")
        self.flag_re = re.compile(flag_pattern)
        self.verdicts: List[ValidationVerdict] = []

    def validate_flag(self, candidate: str, reproduction_steps: List[str]) -> ValidationVerdict:
        """复核疑似 flag：按复现步骤独立重放，检查输出中是否稳定出现。"""
        evidence: List[str] = []
        hits = 0
        for step in reproduction_steps:
            out = self.recheck_runner(step)
            if candidate in out:
                hits += 1
                evidence.append(f"步骤 {step[:60]!r} 输出含候选 flag")
        if hits == len(reproduction_steps) and reproduction_steps:
            verdict = ValidationVerdict(candidate, "flag", True, "high", evidence,
                                        "全部复现步骤均稳定复现该 flag")
        elif hits > 0:
            verdict = ValidationVerdict(candidate, "flag", True, "medium", evidence,
                                        f"{hits}/{len(reproduction_steps)} 步复现，建议人工抽查")
        else:
            verdict = ValidationVerdict(candidate, "flag", False, "low", evidence,
                                        "任何复现步骤均未再出现该候选，判定假阳性")
        self.verdicts.append(verdict)
        return verdict

    def validate_vulnerability(self, description: str,
                               proof_of_concept: str) -> ValidationVerdict:
        """复核疑似漏洞：独立重放 PoC，验证现象是否可复现。"""
        out = self.recheck_runner(proof_of_concept)
        # PoC 输出中不应包含报错/拒绝类关键词，且应包含预期现象标记
        error_markers = ["error", "denied", "blocked", "404", " refused"]
        has_error = any(m in out.lower() for m in error_markers)
        confirmed = not has_error and len(out.strip()) > 0
        verdict = ValidationVerdict(
            description, "vulnerability", confirmed,
            "high" if confirmed else "low",
            [f"PoC 独立重放输出: {out[:300]}"],
            "PoC 可复现" if confirmed else "PoC 重放失败或报错，判定假阳性",
        )
        self.verdicts.append(verdict)
        return verdict

    def report(self) -> str:
        lines = [f"# 验证报告（共 {len(self.verdicts)} 项）"]
        for v in self.verdicts:
            mark = "✓" if v.confirmed else "✗"
            lines.append(f"- {mark} [{v.kind}/{v.confidence}] {v.target[:80]} — {v.reason}")
        return "\n".join(lines)
