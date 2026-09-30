"""Pentesting Task Tree（PTT）—— 树形任务状态追踪（P1，对标 PentestGPT）。

核心约束（防幻觉篡改）：
- LLM 每轮可以提交状态更新，但**只允许修改叶子节点**。
- 任何试图新增/删除/改写非叶子节点的更新都会被拒绝并记录，
  防止模型在 long context 中悄悄篡改整体任务结构。
- PentestGPT 消融显示：去掉全局状态追踪，完成率掉到 53.6%。
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional


_node_id_counter = itertools.count(1)

VALID_STATUS = ("todo", "in_progress", "done", "failed", "not_applicable")


@dataclass
class PTTNode:
    """任务树节点。内部节点表示阶段，叶子节点表示可执行原子任务。"""

    name: str
    node_id: int = field(default_factory=lambda: next(_node_id_counter))
    status: str = "todo"
    children: List["PTTNode"] = field(default_factory=list)
    note: str = ""

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def find(self, node_id: int) -> Optional["PTTNode"]:
        if self.node_id == node_id:
            return self
        for c in self.children:
            hit = c.find(node_id)
            if hit:
                return hit
        return None


class PTTUpdateRejected(Exception):
    """非法的树更新（试图篡改非叶子节点 / 结构变更）。"""


class PentestingTaskTree:
    """带完整性校验的渗透任务树。"""

    # 标准 CTF 渗透阶段骨架（内部节点），叶子由具体题目填充
    DEFAULT_STAGES = ["信息收集", "漏洞识别", "漏洞利用", "flag提取与验证"]

    def __init__(self, challenge_name: str = "") -> None:
        self.root = PTTNode(name=challenge_name or "challenge")
        for stage in self.DEFAULT_STAGES:
            self.root.children.append(PTTNode(name=stage))
        self.rejected_updates: List[str] = []

    # -- 初始化叶子 -----------------------------------------------------------

    def add_leaf(self, stage_node_id: int, task_name: str) -> PTTNode:
        """在指定阶段下挂一个原子任务（仅初始化期/Planner 显式调用）。"""
        stage = self.root.find(stage_node_id)
        if stage is None:
            raise KeyError(f"节点 #{stage_node_id} 不存在")
        leaf = PTTNode(name=task_name)
        stage.children.append(leaf)
        return leaf

    # -- 受限更新（核心防幻觉机制） ---------------------------------------------

    def apply_update(self, node_id: int, status: Optional[str] = None,
                     note: Optional[str] = None,
                     new_children: Optional[List[str]] = None) -> PTTNode:
        """LLM 提交的单节点更新。

        只允许：
        - 修改**叶子节点**的 status / note。
        拒绝并记录：
        - 修改内部节点状态（阶段状态由叶子自动汇总）。
        - 试图给节点增删子节点（结构变更）。
        """
        node = self.root.find(node_id)
        if node is None:
            self._reject(f"更新指向不存在的节点 #{node_id}")
            raise PTTUpdateRejected(f"节点 #{node_id} 不存在")

        if new_children is not None:
            self._reject(f"试图变更节点 #{node_id} 的子结构（新增 {new_children}）")
            raise PTTUpdateRejected("LLM 更新不允许变更树结构，仅 Planner 可增删节点")

        if not node.is_leaf:
            self._reject(f"试图直接修改内部节点 #{node_id}({node.name}) 的状态")
            raise PTTUpdateRejected(
                f"节点 #{node_id} 是内部节点，只能修改叶子节点；"
                "内部节点状态由叶子自动汇总")

        if status is not None:
            if status not in VALID_STATUS:
                self._reject(f"非法状态 {status!r}")
                raise PTTUpdateRejected(f"非法状态 {status!r}，合法值: {VALID_STATUS}")
            node.status = status
        if note is not None:
            node.note = note[:500]
        return node

    # -- 状态汇总 -----------------------------------------------------------

    def refresh_internal_status(self) -> None:
        """自底向上汇总内部节点状态（代码计算，不给 LLM 改的机会）。"""
        def summarize(node: PTTNode) -> str:
            if node.is_leaf:
                return node.status
            child_status = [summarize(c) for c in node.children]
            if not child_status:
                node.status = "todo"
            elif all(s == "done" for s in child_status):
                node.status = "done"
            elif all(s in ("failed", "not_applicable") for s in child_status):
                node.status = "failed"
            elif any(s == "in_progress" for s in child_status):
                node.status = "in_progress"
            else:
                node.status = "todo"
            return node.status
        summarize(self.root)

    # -- 视图 ---------------------------------------------------------------

    def render(self) -> str:
        self.refresh_internal_status()
        icons = {"todo": "⬜", "in_progress": "🔄", "done": "✅",
                 "failed": "❌", "not_applicable": "➖"}
        lines: List[str] = []

        def walk(node: PTTNode, depth: int) -> None:
            note = f" — {node.note}" if node.note else ""
            lines.append(
                "  " * depth + f"{icons[node.status]} #{node.node_id} {node.name}{note}")
            for c in node.children:
                walk(c, depth + 1)

        walk(self.root, 0)
        return "\n".join(lines)

    def next_actionable(self) -> List[PTTNode]:
        """列出全部可执行叶子（todo 状态），供 Planner 挑选。"""
        leaves: List[PTTNode] = []

        def walk(node: PTTNode) -> None:
            if node.is_leaf and node.status == "todo":
                leaves.append(node)
            for c in node.children:
                walk(c)

        walk(self.root)
        return leaves

    def _reject(self, reason: str) -> None:
        self.rejected_updates.append(reason)
