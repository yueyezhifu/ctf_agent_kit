"""日志/流量分析器（蓝队模块，骨架但核心逻辑可用）。

能力：
1. IOC 规则匹配：按正则规则扫描日志行，产出结构化告警。
2. 异常统计：状态码分布、Top IP、单位时间请求速率突增检测。
3. 攻击链还原：把同一来源的告警按时间排序，输出攻击时间线。

输入兼容常见文本日志（nginx/apache access、auth.log）与
tshark -T fields 导出的行式流量记录。纯标准库实现。
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Pattern


@dataclass
class IoCRule:
    """一条 IOC（入侵指标）匹配规则。"""

    name: str
    pattern: str
    severity: str = "medium"   # low / medium / high / critical
    category: str = "unknown"  # sqli / xss / lfi / brute_force / scan ...
    compiled: Optional[Pattern] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.compiled = re.compile(self.pattern, re.I)


# 内置规则库：覆盖 CTF/靶场常见攻击特征
DEFAULT_RULES: List[IoCRule] = [
    IoCRule("SQL 注入", r"(\bunion\b.*\bselect\b)|(\bor\b\s+\d+=\d+)|('|--|/\*)", "high", "sqli"),
    IoCRule("路径穿越/LFI", r"\.\./|\.\.\\|(php://|file://|/etc/passwd)", "high", "lfi"),
    IoCRule("XSS 探测", r"<script|javascript:|onerror=|onload=", "medium", "xss"),
    IoCRule("命令注入", r"[;&|`]\s*(cat|id|whoami|nc|curl|wget)\b", "critical", "rce"),
    IoCRule("目录扫描", r"\b(phpmyadmin|\.git|\.env|wp-admin|backup\.(zip|sql))\b", "medium", "scan"),
    IoCRule("爆破尝试", r"(failed password|authentication failure|invalid user)", "medium", "brute_force"),
    IoCRule("Webshell 特征", r"\b(eval|assert|system|passthru|shell_exec)\s*\(", "critical", "webshell"),
    IoCRule("反弹shell", r"(bash -i|/dev/tcp/|nc -e|mkfifo)", "critical", "reverse_shell"),
]


@dataclass
class Alert:
    rule: str
    severity: str
    category: str
    line_no: int
    excerpt: str
    source_ip: str = ""
    timestamp: str = ""


class LogAnalyzer:
    """日志/流量分析器。"""

    IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    def __init__(self, rules: Optional[List[IoCRule]] = None) -> None:
        self.rules = rules or list(DEFAULT_RULES)
        self.alerts: List[Alert] = []

    # -- IOC 扫描 -----------------------------------------------------------

    def scan_lines(self, lines: Iterable[str]) -> List[Alert]:
        """逐行 IOC 扫描，产出告警列表。"""
        for i, line in enumerate(lines, 1):
            for rule in self.rules:
                if rule.compiled and rule.compiled.search(line):
                    self.alerts.append(Alert(
                        rule=rule.name, severity=rule.severity,
                        category=rule.category, line_no=i,
                        excerpt=line.strip()[:300],
                        source_ip=self._first_ip(line),
                    ))
        return self.alerts

    # -- 异常统计 ---------------------------------------------------------------

    def top_ips(self, lines: Iterable[str], top: int = 10) -> List[tuple]:
        counter: Counter = Counter()
        for line in lines:
            ip = self._first_ip(line)
            if ip:
                counter[ip] += 1
        return counter.most_common(top)

    def status_code_distribution(self, lines: Iterable[str]) -> Dict[str, int]:
        dist: Counter = Counter()
        code_re = re.compile(r'" \s*(\d{3})\s')
        for line in lines:
            m = code_re.search(line)
            if m:
                dist[m.group(1)] += 1
        return dict(dist.most_common())

    def detect_rate_spike(self, timestamps: List[float],
                          window_seconds: float = 60.0,
                          threshold_factor: float = 3.0) -> List[tuple]:
        """滑动窗口速率突增检测：窗口速率超过全局均值 N 倍即报。

        返回 [(窗口起点, 窗口内请求数), ...]。
        """
        if len(timestamps) < 2:
            return []
        ts = sorted(timestamps)
        total_span = max(ts[-1] - ts[0], 1.0)
        global_rate = len(ts) / total_span
        spikes: List[tuple] = []
        left = 0
        for right, t in enumerate(ts):
            while ts[left] < t - window_seconds:
                left += 1
            count = right - left + 1
            if count > global_rate * window_seconds * threshold_factor and count >= 10:
                spikes.append((t, count))
        return spikes

    # -- 攻击链还原 ---------------------------------------------------------------

    def attack_timeline(self, source_ip: Optional[str] = None) -> str:
        """按行号（时间序）输出某来源（或全部）的攻击时间线。"""
        alerts = self.alerts
        if source_ip:
            alerts = [a for a in alerts if a.source_ip == source_ip]
        alerts = sorted(alerts, key=lambda a: a.line_no)
        lines = [f"# 攻击时间线{f'（来源 {source_ip}）' if source_ip else ''}",
                 f"共 {len(alerts)} 条告警，生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}"]
        for a in alerts:
            lines.append(
                f"- 行{a.line_no} [{a.severity}/{a.category}] {a.rule}: {a.excerpt[:120]}")
        return "\n".join(lines)

    def summary(self) -> str:
        by_sev = Counter(a.severity for a in self.alerts)
        by_cat = Counter(a.category for a in self.alerts)
        lines = [f"告警总数: {len(self.alerts)}",
                 f"按严重度: {dict(by_sev)}",
                 f"按类别: {dict(by_cat)}"]
        return "\n".join(lines)

    @classmethod
    def _first_ip(cls, line: str) -> str:
        m = cls.IP_RE.search(line)
        return m.group(0) if m else ""
