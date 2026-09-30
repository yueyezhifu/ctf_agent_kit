"""核心机制：flag 验证、预算控制、结构化笔记、幻觉防护、PTT、并行采样。"""

from .flag_verifier import FlagVerifier, FlagFormatConfig, SubmissionResult
from .budget import Budget, BudgetExceeded, GiveUp, CATEGORY_BUDGETS
from .notes import Notebook, Fact, AttemptedPath
from .guardrails import Guardrails, Claim, GuardrailReport

__all__ = [
    "FlagVerifier", "FlagFormatConfig", "SubmissionResult",
    "Budget", "BudgetExceeded", "GiveUp", "CATEGORY_BUDGETS",
    "Notebook", "Fact", "AttemptedPath",
    "Guardrails", "Claim", "GuardrailReport",
]
