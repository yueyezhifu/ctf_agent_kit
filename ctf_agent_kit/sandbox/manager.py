"""沙箱管理器：题目 metadata schema + docker-compose 生命周期。

题目目录结构约定::

    challenges/<challenge_id>/
        metadata.json        # 题目元数据（schema 见 ChallengeMeta）
        start.sh             # 启动脚本（可选，compose 内或宿主机执行）
        attachments/         # 题目附件
        docker-compose.yml   # 可由模板渲染生成

Compose 模板见 ``templates/docker-compose.yml``（string.Template 变量替换）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Dict, List, Optional

TEMPLATE_PATH = Path(__file__).parent / "templates" / "docker-compose.yml"

VALID_CATEGORIES = ("crypto", "reverse", "pwn", "web", "forensics", "misc")


class MetadataError(ValueError):
    """题目 metadata 不合 schema。"""


@dataclass
class ChallengeMeta:
    """题目元数据 schema。

    metadata.json 示例::

        {
          "id": "example_caesar",
          "category": "crypto",
          "title": "凯撒的秘密",
          "description": "解密附件中的密文",
          "flag_patterns": ["flag\\\\{[^}]+\\\\}"],
          "flag": "flag{c4es4r_1s_we4k}",
          "start_script": "start.sh",
          "ports": [1337],
          "timeout_seconds": 1800
        }
    """

    id: str
    category: str
    title: str
    description: str
    flag_patterns: List[str] = field(default_factory=list)
    flag: Optional[str] = None            # 本地评测时可直接内置标准答案
    start_script: str = "start.sh"
    ports: List[int] = field(default_factory=list)
    timeout_seconds: int = 1800
    extra: Dict = field(default_factory=dict)

    REQUIRED = ("id", "category", "title", "description")

    @classmethod
    def load(cls, challenge_dir: str) -> "ChallengeMeta":
        path = Path(challenge_dir) / "metadata.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in cls.REQUIRED:
            if key not in data:
                raise MetadataError(f"metadata 缺少必填字段 {key!r}: {path}")
        if data["category"] not in VALID_CATEGORIES:
            raise MetadataError(
                f"非法类别 {data['category']!r}，合法值: {VALID_CATEGORIES}")
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        extra = {k: v for k, v in data.items() if k not in known}
        kwargs = {k: v for k, v in data.items() if k in known and k != "extra"}
        return cls(extra=extra, **kwargs)


@dataclass
class Sandbox:
    """一个运行中的题目沙箱实例。"""

    meta: ChallengeMeta
    workdir: Path
    started_at: float = field(default_factory=time.time)
    running: bool = False

    @property
    def endpoints(self) -> List[str]:
        """题目对外暴露的服务地址（本机映射端口）。"""
        return [f"127.0.0.1:{p}" for p in self.meta.ports]


class SandboxManager:
    """沙箱生命周期管理：渲染 compose → up → down → 清理。"""

    def __init__(self, challenges_root: str, docker_bin: str = "docker") -> None:
        self.challenges_root = Path(challenges_root)
        self.docker_bin = docker_bin
        self.active: Dict[str, Sandbox] = {}

    def load_challenge(self, challenge_id: str) -> ChallengeMeta:
        return ChallengeMeta.load(str(self.challenges_root / challenge_id))

    def render_compose(self, meta: ChallengeMeta, dest_dir: Optional[str] = None) -> Path:
        """用模板渲染该题的 docker-compose.yml。"""
        template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
        ports_block = "\n".join(f'      - "{p}:{p}"' for p in meta.ports) or "      []"
        content = template.safe_substitute(
            challenge_id=meta.id,
            category=meta.category,
            ports=ports_block,
            timeout_seconds=str(meta.timeout_seconds),
        )
        out_dir = Path(dest_dir) if dest_dir else self.challenges_root / meta.id
        out = out_dir / "docker-compose.yml"
        out.write_text(content, encoding="utf-8")
        return out

    def up(self, challenge_id: str) -> Sandbox:
        """启动题目沙箱（每题独立 compose project，相互隔离）。"""
        meta = self.load_challenge(challenge_id)
        workdir = self.challenges_root / challenge_id
        if not (workdir / "docker-compose.yml").exists():
            self.render_compose(meta)
        self._compose(challenge_id, "up", "-d", "--wait")
        sb = Sandbox(meta=meta, workdir=workdir, running=True)
        self.active[challenge_id] = sb
        return sb

    def down(self, challenge_id: str, purge: bool = False) -> None:
        """停止并回收沙箱；purge=True 时连数据卷一起删。"""
        args = ["down", "-v"] if purge else ["down"]
        self._compose(challenge_id, *args)
        sb = self.active.pop(challenge_id, None)
        if sb:
            sb.running = False

    def is_available(self) -> bool:
        """检测 docker 是否可用（骨架环境下允许降级为纯本地执行）。"""
        return shutil.which(self.docker_bin) is not None

    def _compose(self, challenge_id: str, *args: str) -> None:
        workdir = self.challenges_root / challenge_id
        cmd = [self.docker_bin, "compose",
               "-p", f"ctf_{challenge_id}",  # 独立 project 名 → 隔离
               *args]
        proc = subprocess.run(cmd, cwd=str(workdir),
                              capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"docker compose {' '.join(args)} 失败: {proc.stderr[:500]}")
