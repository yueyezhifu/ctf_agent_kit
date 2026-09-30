"""题库回放机制（学习优化）。

历史解题轨迹归档与检索：
- 每题轨迹（成功/失败/笔记/复盘）归档为 JSONL，落盘持久化。
- 支持按类别/结果/知识点检索回放，供：
  1. 错题重练（间隔重复调度，见 review.py 的 SPACED_INTERVALS）
  2. few-shot 示例挑选（同类成功轨迹喂给新题）
  3. writeup 库的原始素材（rag/writeup_store 联动）
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TrajectoryRecord:
    """一条归档的解题轨迹。"""

    challenge_id: str
    category: str
    solved: bool
    rounds: int
    cost_usd: float
    flag: Optional[str] = None
    notebook_snapshot: str = ""     # Notebook.render() 快照
    review_markdown: str = ""       # 复盘报告
    knowledge_points: List[str] = field(default_factory=list)
    attempts_count: int = 0         # 第几次挑战该题（错题重练计数）
    recorded_at: float = field(default_factory=time.time)


class ReplayArchive:
    """题库回放归档库（JSONL 追加写 + 内存索引）。"""

    def __init__(self, archive_path: str) -> None:
        self.archive_path = Path(archive_path)
        self.archive_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: List[TrajectoryRecord] = []
        self._load()

    # -- 读写 ---------------------------------------------------------------

    def _load(self) -> None:
        if not self.archive_path.exists():
            return
        for line in self.archive_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                data = json.loads(line)
                self.records.append(TrajectoryRecord(**data))

    def save(self, record: TrajectoryRecord) -> None:
        """追加归档一条轨迹。"""
        # 同题重练计数
        record.attempts_count = sum(
            1 for r in self.records if r.challenge_id == record.challenge_id) + 1
        with self.archive_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        self.records.append(record)

    # -- 检索回放 ---------------------------------------------------------------

    def by_category(self, category: str) -> List[TrajectoryRecord]:
        return [r for r in self.records if r.category == category]

    def unsolved(self) -> List[TrajectoryRecord]:
        """错题集：至今未解出的题（取每题最近一次记录）。"""
        latest: Dict[str, TrajectoryRecord] = {}
        for r in self.records:
            latest[r.challenge_id] = r
        return [r for r in latest.values() if not r.solved]

    def due_for_review(self, now: Optional[float] = None) -> List[TrajectoryRecord]:
        """到期该重练的错题（配合复盘里的 next_review_at）。"""
        # next_review_at 存在 review_markdown 外部字段；这里按记录时间与重练次数估算
        now = now or time.time()
        due = []
        for r in self.unsolved():
            intervals = [86400, 3 * 86400, 7 * 86400, 14 * 86400]
            idx = min(r.attempts_count - 1, len(intervals) - 1)
            if r.recorded_at + intervals[idx] <= now:
                due.append(r)
        return due

    def few_shot_pool(self, category: str, limit: int = 3) -> List[TrajectoryRecord]:
        """挑同类成功轨迹作 few-shot 素材（短轮次优先——干净利落的轨迹更好教）。"""
        solved = [r for r in self.by_category(category) if r.solved]
        solved.sort(key=lambda r: r.rounds)
        return solved[:limit]

    def stats(self) -> Dict:
        by_cat: Dict[str, Dict[str, int]] = {}
        for r in self.records:
            c = by_cat.setdefault(r.category, {"total": 0, "solved": 0})
            c["total"] += 1
            c["solved"] += int(r.solved)
        return {
            "total_records": len(self.records),
            "by_category": by_cat,
            "unsolved_count": len(self.unsolved()),
            "due_for_review": len(self.due_for_review()),
        }
