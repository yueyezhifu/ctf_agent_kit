"""题型自动分类器（学习优化）。

按题目描述 + 附件特征判定六大类别（crypto/reverse/pwn/web/forensics/misc）。
规则法实现：关键词加权打分 + 附件类型强特征 + 兜底 misc。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CATEGORIES = ("crypto", "reverse", "pwn", "web", "forensics", "misc")

# 关键词权重表：词 → (类别, 权重)
KEYWORD_RULES: List[Tuple[re.Pattern, str, float]] = [
    # crypto
    (re.compile(r"\b(rsa|aes|des|ecc|cipher|encrypt|decrypt|openssl|"
                r"padding oracle|公钥|私钥|加密|解密|密文)\b", re.I), "crypto", 3.0),
    (re.compile(r"\b(pubkey|\.pem|modulus|exponent)\b", re.I), "crypto", 2.0),
    # reverse
    (re.compile(r"\b(crackme|reverse|逆向|反编译|keygen|serial|"
                r"脱壳|加壳|packed|obfuscat\w+)\b", re.I), "reverse", 3.0),
    # pwn
    (re.compile(r"\b(pwn|bof|overflow|溢出|格式化字符串|heap|堆|"
                r"uaf|rop|shellcode|nc\s+\S+\s+\d+)\b", re.I), "pwn", 3.0),
    (re.compile(r"\blibc\.so|ld-linux", re.I), "pwn", 2.5),
    # web
    (re.compile(r"\b(http://|https://|url|网站|登录|admin|"
                r"sqli|xss|ssrf|ssti|upload|上传|cookie|jwt)\b", re.I), "web", 3.0),
    (re.compile(r"\b(php|flask|django|spring|nginx|apache)\b", re.I), "web", 1.5),
    # forensics
    (re.compile(r"\b(pcap|pcapng|流量|取证|forensic|memory dump|内存|"
                r"磁盘镜像|volatility|wireshark|日志分析|incident)\b", re.I), "forensics", 3.0),
    # misc
    (re.compile(r"\b(misc|杂项|隐写|stego|编码|puzzle|osint|二维码)\b", re.I), "misc", 2.0),
]

# 附件扩展名 → (类别, 权重) 强特征
EXTENSION_RULES: Dict[str, Tuple[str, float]] = {
    ".pcap": ("forensics", 4.0), ".pcapng": ("forensics", 4.0),
    ".mem": ("forensics", 4.0), ".dmp": ("forensics", 3.5),
    ".img": ("forensics", 3.0), ".vmem": ("forensics", 4.0),
    ".pem": ("crypto", 3.5), ".pub": ("crypto", 2.5),
    ".pyc": ("reverse", 3.5), ".class": ("reverse", 3.0),
    ".apk": ("reverse", 3.0), ".dex": ("reverse", 3.5),
    ".exe": ("reverse", 2.0), ".dll": ("reverse", 1.5),
    ".php": ("web", 2.0), ".jsp": ("web", 2.5), ".war": ("web", 2.5),
    ".png": ("misc", 1.0), ".jpg": ("misc", 1.0),
    ".wav": ("misc", 1.5), ".mp3": ("misc", 1.5),
}


def classify(description: str = "",
             attachments: Optional[List[str]] = None,
             has_remote_service: bool = False,
             has_binary: bool = False) -> str:
    """综合判类别，返回六大类之一。"""
    scores, _ = score(description, attachments, has_remote_service, has_binary)
    if not scores or max(scores.values()) <= 0:
        return "misc"
    return max(scores.items(), key=lambda kv: kv[1])[0]


def score(description: str = "",
          attachments: Optional[List[str]] = None,
          has_remote_service: bool = False,
          has_binary: bool = False) -> Tuple[Dict[str, float], List[str]]:
    """返回各类别得分与命中理由（可解释性，供复盘用）。"""
    scores: Dict[str, float] = {c: 0.0 for c in CATEGORIES}
    reasons: List[str] = []

    for rule, cat, w in KEYWORD_RULES:
        m = rule.search(description or "")
        if m:
            scores[cat] += w
            reasons.append(f"关键词 {m.group(0)!r} → {cat} (+{w})")

    for att in attachments or []:
        suffix = Path(att).suffix.lower()
        if suffix in EXTENSION_RULES:
            cat, w = EXTENSION_RULES[suffix]
            scores[cat] += w
            reasons.append(f"附件 {att} ({suffix}) → {cat} (+{w})")
        # 无扩展名的 ELF 可执行文件：rev/pwn 倾向
        if suffix == "" and Path(att).name not in ("README",):
            scores["pwn"] += 0.5
            scores["reverse"] += 0.5

    if has_remote_service:
        # nc 类远端服务：pwn 居多；http 已在关键词里命中 web
        if not re.search(r"https?://", description or ""):
            scores["pwn"] += 1.5
            reasons.append("存在远端服务(非HTTP) → pwn (+1.5)")
    if has_binary:
        scores["pwn"] += 1.0
        scores["reverse"] += 1.0
        reasons.append("含二进制 → pwn/reverse (+1.0)")

    return scores, reasons


def classify_with_reasons(description: str = "",
                          attachments: Optional[List[str]] = None,
                          **kwargs) -> Tuple[str, List[str]]:
    """分类 + 命中理由（错题归档/复盘用）。"""
    scores, reasons = score(description, attachments, **kwargs)
    if not scores or max(scores.values()) <= 0:
        return "misc", ["无特征命中，兜底 misc"]
    best = max(scores.items(), key=lambda kv: kv[1])[0]
    return best, reasons
