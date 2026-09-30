"""红队攻击模块：六大类攻击 playbook。

playbooks/ 下每类一份 Markdown（题型特征识别→常用工具→标准攻击链→常见变体），
由 AutoPrompter 按题型注入 Executor 指令。
"""

from pathlib import Path

PLAYBOOKS_DIR = Path(__file__).parent / "playbooks"


def load_playbook(category: str) -> str:
    """读取某类别的攻击 playbook；不存在时返回空串。"""
    path = PLAYBOOKS_DIR / f"{category}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""
