"""检索增强：writeup 库与自我反思式检索（P2，对标 CRAKEN）。

机制：
1. 本地 writeup 库（Markdown/JSONL），按类别 + 关键词建立倒排索引。
2. 失败时自我反思式检索：把失败轨迹摘要成 query → 检索相似 writeup →
   提取其中的「洞见」转成 knowledge-hint 注入下一轮 prompt（CRAKEN，+3pt 到 22%）。
纯标准库实现（TF 打分 + 倒排索引），接口预留向量检索升级位。
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_WORD_RE = re.compile(r"[A-Za-z0-9_]{2,}|[一-鿿]")


@dataclass
class Writeup:
    """一篇历史 writeup。"""

    writeup_id: str
    title: str
    category: str
    content: str
    tags: List[str] = field(default_factory=list)
    knowledge_points: List[str] = field(default_factory=list)


@dataclass
class RetrievalHit:
    writeup: Writeup
    score: float


@dataclass
class KnowledgeHint:
    """注入 prompt 的知识提示。"""

    hint: str
    source_writeup_id: str
    relevance: float


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


class WriteupStore:
    """本地 writeup 库：加载、索引、检索。"""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.writeups: Dict[str, Writeup] = {}
        self._inverted: Dict[str, set] = defaultdict(set)  # term → writeup_ids
        self._tf: Dict[str, Counter] = {}                  # id → term 计数

    # -- 加载与索引 -----------------------------------------------------------

    def load_all(self) -> int:
        """扫描库目录：.jsonl 逐行一条；.md 一篇一条（front-matter 可选）。"""
        self.root.mkdir(parents=True, exist_ok=True)
        count = 0
        for path in sorted(self.root.rglob("*")):
            if path.suffix == ".jsonl":
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        self.add(Writeup(**json.loads(line)))
                        count += 1
            elif path.suffix == ".md":
                self.add(self._from_markdown(path))
                count += 1
        return count

    def add(self, writeup: Writeup) -> None:
        self.writeups[writeup.writeup_id] = writeup
        terms = _tokenize(writeup.title + " " + writeup.content + " "
                          + " ".join(writeup.tags + writeup.knowledge_points))
        self._tf[writeup.writeup_id] = Counter(terms)
        for t in set(terms):
            self._inverted[t].add(writeup.writeup_id)

    # -- 检索 -----------------------------------------------------------------

    def search(self, query: str, category: Optional[str] = None,
               top_k: int = 3) -> List[RetrievalHit]:
        """TF-IDF 风格的简易打分检索。"""
        terms = _tokenize(query)
        if not terms:
            return []
        n_docs = max(len(self.writeups), 1)
        scores: Dict[str, float] = defaultdict(float)
        for term in terms:
            docs = self._inverted.get(term, set())
            idf = math.log(1 + n_docs / (1 + len(docs)))
            for wid in docs:
                scores[wid] += self._tf[wid].get(term, 0) * idf
        hits = []
        for wid, score in scores.items():
            w = self.writeups[wid]
            if category and w.category != category:
                score *= 0.3  # 跨类别降权而非剔除
            hits.append(RetrievalHit(w, round(score, 4)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    # -- 自我反思式检索（CRAKEN） ------------------------------------------------

    def reflect_and_retrieve(self, failure_summary: str, category: str,
                             top_k: int = 2) -> List[KnowledgeHint]:
        """失败 → 反思 query → 检索 → 提炼 knowledge-hint。

        反思 query 由失败摘要中的关键信号（报错词、工具名、协议名）组成；
        真实部署时此 query 可由 LLM 生成，本骨架用规则抽取。
        """
        keywords = self._extract_reflection_keywords(failure_summary)
        query = " ".join(keywords) or failure_summary[:200]
        hints: List[KnowledgeHint] = []
        for hit in self.search(query, category=category, top_k=top_k):
            kp = "、".join(hit.writeup.knowledge_points) or hit.writeup.title
            hints.append(KnowledgeHint(
                hint=(f"[相似 writeup《{hit.writeup.title}》] 关键知识点: {kp}。"
                      f"可参考思路: {hit.writeup.content[:300]}"),
                source_writeup_id=hit.writeup.writeup_id,
                relevance=hit.score,
            ))
        return hints

    @staticmethod
    def _extract_reflection_keywords(failure_summary: str) -> List[str]:
        """从失败摘要抽取检索关键词（报错、协议、工具、算法名）。"""
        patterns = [
            r"\b(error|failed|denied|timeout|SIGSEGV|stack|heap|overflow)\b",
            r"\b(rsa|aes|des|ecc|xor|padding|oracle)\b",
            r"\b(sqli|xss|ssrf|lfi|rfi|rce|jwt|ssti)\b",
            r"\b(pcap|icmp|dns|http|usb|memory|dump)\b",
            r"\b(upx|packed|stripped|obfuscat\w*)\b",
        ]
        found: List[str] = []
        for p in patterns:
            found.extend(m.lower() for m in re.findall(p, failure_summary, re.I))
        return list(dict.fromkeys(found))[:8]

    def render_hints(self, hints: List[KnowledgeHint]) -> str:
        """渲染为可注入 prompt 的 knowledge-hint 块。"""
        if not hints:
            return ""
        lines = ["【检索到的相关知识提示】"]
        for h in hints:
            lines.append(f"- （相关度 {h.relevance}）{h.hint}")
        return "\n".join(lines)

    def _from_markdown(self, path: Path) -> Writeup:
        text = path.read_text(encoding="utf-8")
        category = path.parent.name if path.parent.name in (
            "crypto", "reverse", "pwn", "web", "forensics", "misc") else "misc"
        title = path.stem
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        return Writeup(writeup_id=path.stem, title=title, category=category,
                       content=text)
