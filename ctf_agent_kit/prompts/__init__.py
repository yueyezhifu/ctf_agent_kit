"""prompts 包：六大类解题演示（Markdown few-shot 轨迹）。

demos/ 目录下每类一份 Markdown，由 AutoPrompter 按题型注入。
"""

from pathlib import Path

DEMOS_DIR = Path(__file__).parent / "demos"


def load_demo(category: str) -> str:
    """读取某类别的解题演示文本；不存在时返回空串。"""
    path = DEMOS_DIR / f"{category}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""
