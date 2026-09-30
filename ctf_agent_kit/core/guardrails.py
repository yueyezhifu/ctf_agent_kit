"""幻觉防护（P0）。

对应优化方案 P0-4：
1. 结论必须绑定真实工具输出证据（evidence-bound conclusions）。
2. 检测无工具调用的「自言自语」（soliloquizing）轨迹并强制纠正：
   连续多轮只有文本输出、没有任何工具调用，却声称获得新信息，
   是典型的幻觉信号。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Claim:
    """一条结论声明及其绑定的证据。"""

    content: str
    evidence_tool_call_id: Optional[str] = None  # 必须指向一次真实工具调用
    evidence_excerpt: str = ""                   # 工具输出原文摘录


@dataclass
class GuardrailReport:
    ok: bool
    violations: List[str] = field(default_factory=list)
    corrective_prompt: str = ""  # 违例时注入下一轮 prompt 的纠偏指令


# 结论性措辞：出现这些词却拿不出证据时重点审查
CLAIM_MARKERS = [
    "flag 是", "flag为", "the flag is", "得到flag", "拿到flag",
    "漏洞存在于", "确认存在漏洞", "成功利用", "解密得到", "密码是",
]


class Guardrails:
    """轨迹级幻觉守门员。"""

    def __init__(self, soliloquy_threshold: int = 3) -> None:
        # 连续多少轮无工具调用即判定为自言自语
        self.soliloquy_threshold = soliloquy_threshold
        self._tool_call_ids: set = set()
        self._rounds_without_tools = 0

    # -- 工具调用登记 -------------------------------------------------------

    def register_tool_call(self, call_id: str) -> None:
        """每发生一次真实工具调用就登记，供结论证据校验。"""
        self._tool_call_ids.add(call_id)
        self._rounds_without_tools = 0

    def note_round_without_tools(self) -> None:
        """一轮结束仍无工具调用时调用。"""
        self._rounds_without_tools += 1

    # -- 检查 ---------------------------------------------------------------

    def check_claim(self, claim: Claim) -> GuardrailReport:
        """校验单条结论是否绑定了真实工具输出。"""
        violations: List[str] = []
        if claim.evidence_tool_call_id is None:
            violations.append(f"结论未绑定任何工具调用: {claim.content[:80]}")
        elif claim.evidence_tool_call_id not in self._tool_call_ids:
            violations.append(
                f"结论引用了不存在的工具调用 {claim.evidence_tool_call_id}: "
                f"{claim.content[:80]}"
            )
        if not claim.evidence_excerpt.strip():
            violations.append(f"结论缺少工具输出原文摘录: {claim.content[:80]}")
        return self._report(violations)

    def check_round(self, assistant_text: str, had_tool_call: bool) -> GuardrailReport:
        """检查一整轮轨迹。

        - 有工具调用 → 归零自言自语计数。
        - 无工具调用但出现结论性措辞 → 警告。
        - 连续 N 轮无工具调用 → 强制纠正（要求必须调用工具或 give_up）。
        """
        violations: List[str] = []
        if had_tool_call:
            self._rounds_without_tools = 0
            return self._report(violations)

        self._rounds_without_tools += 1

        for marker in CLAIM_MARKERS:
            if marker in assistant_text:
                violations.append(
                    f"无工具调用的轮次中出现结论性措辞 {marker!r}，疑似幻觉"
                )
                break

        if self._rounds_without_tools >= self.soliloquy_threshold:
            violations.append(
                f"已连续 {self._rounds_without_tools} 轮无工具调用（自言自语轨迹），"
                "必须立即调用真实工具验证假设，或确认无解后 give_up"
            )
        return self._report(violations)

    # -- 纠偏 ---------------------------------------------------------------

    @staticmethod
    def _report(violations: List[str]) -> GuardrailReport:
        if not violations:
            return GuardrailReport(ok=True)
        corrective = (
            "【幻觉防护纠偏】检测到以下违规：\n"
            + "\n".join(f"- {v}" for v in violations)
            + "\n要求：每条结论必须引用一次真实工具调用 ID 及其输出摘录；"
              "不得凭记忆或推测断言 flag / 漏洞。立即用工具验证你的假设。"
        )
        return GuardrailReport(ok=False, violations=violations,
                               corrective_prompt=corrective)


def extract_claim_sentences(text: str) -> List[str]:
    """从助手文本中抽取含结论性措辞的句子（供外层组装 Claim 校验）。"""
    sentences = re.split(r"(?<=[。！？.!?])\s*", text)
    return [s for s in sentences if any(m in s for m in CLAIM_MARKERS)]
