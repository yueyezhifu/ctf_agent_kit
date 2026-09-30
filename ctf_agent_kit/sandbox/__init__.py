"""Docker 沙箱与统一题目封装（P1）。

每题一个独立 docker-compose 环境 + 标准化 metadata（类别/描述/启动脚本），
保证可复现与安全隔离。纯标准库实现：模板渲染 + subprocess 调用 docker compose。
"""

from .manager import ChallengeMeta, Sandbox, SandboxManager

__all__ = ["ChallengeMeta", "Sandbox", "SandboxManager"]
