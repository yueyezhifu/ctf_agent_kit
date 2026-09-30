"""ctf_agent_kit —— CTF 攻防特训智能体工具包。

模块总览：
- models:    模型路由（配置驱动，支持降级链）
- core:      flag 验证、预算控制、结构化笔记、幻觉防护、PTT 任务树、并行采样
- agents:    Planner / Executor / AutoPrompter / Validator 多角色架构
- tools:     pwntools 风格持久 shell、gdb 交互会话
- sandbox:   每题独立 Docker 沙箱与题目封装
- rag:       writeup 检索增强
- bench:     NYU CTF Bench / Cybench 评测
- offense:   红队攻击 playbook
- defense:   蓝队日志分析 / 漏洞成因 / 应急处置
- learning:  题型分类、知识点复盘、题库回放
"""

__version__ = "0.1.0"
