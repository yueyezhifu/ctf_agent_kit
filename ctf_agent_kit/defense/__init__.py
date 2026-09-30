"""蓝队防御模块：日志/流量分析、漏洞成因分析、修复建议、应急处置。

- log_analyzer.py: 日志/流量分析骨架（IOC 规则匹配 + 异常检测）
- playbooks/vuln_root_cause.md: 漏洞成因分析框架
- playbooks/remediation.md: 修复建议模板
- playbooks/incident_checklist.md: 应急处置 checklist
"""

from .log_analyzer import LogAnalyzer, Alert, IoCRule

__all__ = ["LogAnalyzer", "Alert", "IoCRule"]
