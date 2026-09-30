"""模型路由器（纯标准库实现，零第三方依赖）。

职责：
1. 解析 ``config/models.yaml``（内置一个极简 YAML 子集解析器，支持本配置
   使用的「嵌套字典 + 行内列表 + 标量」子集，不依赖 PyYAML）。
2. 按角色（role）返回首选模型与降级链。
3. API key 一律从环境变量读取，配置中只存环境变量名。

更换模型时只需修改 config/models.yaml，业务代码无需改动。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 极简 YAML 子集解析器
# ---------------------------------------------------------------------------

def _parse_scalar(text: str) -> Any:
    """把标量文本解析为 Python 值。"""
    text = text.strip()
    if text == "" :
        return ""
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in inner.split(",")]
    if (text.startswith("'") and text.endswith("'")) or (
        text.startswith('"') and text.endswith('"')
    ):
        return text[1:-1]
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", "none"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _strip_comment(line: str) -> str:
    """去掉行尾注释（不处理引号内的 #，本配置中不会用到）。"""
    if "#" in line:
        return line[: line.index("#")]
    return line


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """解析「嵌套字典 + 行内列表 + 标量」的 YAML 子集。

    支持：
    - 缩进表示的嵌套 mapping
    - ``key: value`` 标量
    - ``key: [a, b, c]`` 行内列表
    - ``#`` 注释与空行

    不支持（本项目配置用不到）：块列表 ``- item``、多行字符串、锚点。
    """
    root: Dict[str, Any] = {}
    # 栈元素为 (缩进宽度, 容器字典)
    stack: List[tuple] = [(-1, root)]

    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"无法解析的行: {raw!r}")
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if value == "":
            child: Dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)
    return root


# ---------------------------------------------------------------------------
# 数据结构与路由器
# ---------------------------------------------------------------------------

@dataclass
class ModelSpec:
    """单个模型的规格描述。"""

    name: str
    model: str
    provider: str = ""
    api_base: str = ""
    api_key_env: str = ""
    max_tokens: int = 8192
    temperature: float = 0.3
    capabilities: List[str] = field(default_factory=list)

    @property
    def api_key(self) -> Optional[str]:
        """从环境变量读取 API key；未设置时返回 None。"""
        if not self.api_key_env:
            return None
        return os.environ.get(self.api_key_env)


@dataclass
class RoleRoute:
    """一个角色的路由：首选模型名 + 降级链（模型名列表）。"""

    primary: str
    fallback_chain: List[str] = field(default_factory=list)


class ModelRouter:
    """按角色路由模型。

    用法::

        router = ModelRouter.from_config("config/models.yaml")
        spec = router.resolve("planner")            # 首选模型
        chain = router.resolution_chain("planner")  # 含降级的完整尝试序列
    """

    def __init__(
        self,
        models: Dict[str, ModelSpec],
        routing: Dict[str, RoleRoute],
        global_fallback: Optional[str] = None,
    ) -> None:
        self.models = models
        self.routing = routing
        self.global_fallback = global_fallback

    # -- 构造 ---------------------------------------------------------------

    @classmethod
    def from_config(cls, path: str) -> "ModelRouter":
        text = Path(path).read_text(encoding="utf-8")
        raw = parse_simple_yaml(text)

        models: Dict[str, ModelSpec] = {}
        for name, cfg in (raw.get("models") or {}).items():
            if not isinstance(cfg, dict):
                continue
            models[name] = ModelSpec(
                name=name,
                model=str(cfg.get("model", "")),
                provider=str(cfg.get("provider", "")),
                api_base=str(cfg.get("api_base", "")),
                api_key_env=str(cfg.get("api_key_env", "")),
                max_tokens=int(cfg.get("max_tokens", 8192)),
                temperature=float(cfg.get("temperature", 0.3)),
                capabilities=list(cfg.get("capabilities") or []),
            )

        routing: Dict[str, RoleRoute] = {}
        for role, cfg in (raw.get("routing") or {}).items():
            if not isinstance(cfg, dict):
                continue
            routing[role] = RoleRoute(
                primary=str(cfg.get("primary", "")),
                fallback_chain=list(cfg.get("fallback_chain") or []),
            )

        return cls(models, routing, raw.get("global_fallback"))

    # -- 查询 ---------------------------------------------------------------

    def resolve(self, role: str) -> ModelSpec:
        """返回角色的首选模型；角色未配置时落到全局兜底。"""
        route = self.routing.get(role)
        name = route.primary if route else None
        if not name or name not in self.models:
            name = self.global_fallback
        if not name or name not in self.models:
            raise KeyError(f"角色 {role!r} 无法路由到任何已配置模型")
        return self.models[name]

    def resolution_chain(self, role: str) -> List[ModelSpec]:
        """返回角色的完整尝试序列：首选 → 降级链 → 全局兜底（去重保序）。"""
        names: List[str] = []
        route = self.routing.get(role)
        if route:
            names.append(route.primary)
            names.extend(route.fallback_chain)
        if self.global_fallback:
            names.append(self.global_fallback)

        seen = set()
        chain: List[ModelSpec] = []
        for n in names:
            if n and n in self.models and n not in seen:
                seen.add(n)
                chain.append(self.models[n])
        if not chain:
            raise KeyError(f"角色 {role!r} 无法路由到任何已配置模型")
        return chain

    def available(self, role: str) -> List[ModelSpec]:
        """返回链上 API key 已就绪（环境变量存在）的模型子集。"""
        return [s for s in self.resolution_chain(role) if s.api_key]
