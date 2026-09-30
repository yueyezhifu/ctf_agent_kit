# 优化方案 → 代码逐条映射表

> 依据工作区《ctf_agent_优化方案.md》（基于 2024–2026 业界调研：EnIGMA、D-CIPHER、CRAKEN、PentestGPT、HPTSA、Cybench、NYU CTF Bench、CAI、XBOW、Naptime）。

## P0 — 低成本高收益

| # | 方案条目 | 代码文件 | 实现要点 |
|---|---|---|---|
| 1 | flag 验证器 + give_up 工具，成功即终止，成本/轮次上限强制退出 | `ctf_agent_kit/core/flag_verifier.py`、`ctf_agent_kit/core/budget.py` | 格式正则配置化（`FlagFormatConfig` 支持 JSON 加载与精确比对）；`submit()` 远端/本地双通道，`scan_and_submit()` 成功短路；`Budget` 四轮上限（轮次/token/成本/时间）+ `GiveUp` 强制退出 + `CATEGORY_BUDGETS` 分类预算 |
| 2 | 类别化 few-shot demonstrations（EnIGMA 消融 +6.2pt） | `ctf_agent_kit/prompts/demos/`（crypto/reverse/pwn/web/forensics/misc 六份 Markdown） | 每份为完整解题轨迹：信息收集→识别→利用→验证，且演示笔记更新与证据绑定 |
| 3 | 结构化笔记替代无限历史 + LM 摘要 | `ctf_agent_kit/core/notes.py` | `Notebook` 三段结构（已知事实/已尝试路径/下一步候选），事实强制带证据字段；长文本走 `SummarizerHook`，未注入时智能截断 |
| 4 | 幻觉防护：结论绑定证据、检测自言自语 | `ctf_agent_kit/core/guardrails.py` | `Guardrails.check_claim()` 校验结论必须引用真实工具调用 ID + 输出摘录；`check_round()` 检测连续 N 轮无工具调用并生成纠偏 prompt |

## P1 — 架构升级

| # | 方案条目 | 代码文件 | 实现要点 |
|---|---|---|---|
| 5 | Planner–Executor 分离 + 失败带详细指令重派 | `ctf_agent_kit/agents/planner.py`、`executor.py`、`auto_prompter.py` | Planner 维护任务列表与修订日志，失败重派插入原位置；Executor 独立会话只回传 `ExecutionResult` 摘要；AutoPrompter 生成首次指令与纠偏重派指令 |
| 6 | 交互式工具（持久 shell、gdb 会话） | `ctf_agent_kit/tools/interactive_shell.py`、`tools/gdb_session.py` | pwntools 语义（recvuntil/sendline/remote/process），纯 socket/subprocess 实现；gdb 走 MI2 接口，结构化解析 stopped 事件（断点/信号/帧） |
| 7 | PTT 状态完整性校验（只允许改叶子节点） | `ctf_agent_kit/core/ptt.py` | `apply_update()` 拒绝内部节点状态修改与任何结构变更并记录；内部节点状态由代码自底向上汇总 |
| 8 | Docker 沙箱 + 统一题目封装 | `ctf_agent_kit/sandbox/`（`manager.py`、`templates/docker-compose.yml`、`challenges/example_caesar/`） | `ChallengeMeta` schema（类别/描述/flag格式/启动脚本/端口/超时）；compose 模板含只读根fs/降权/资源限额；每题独立 compose project 隔离 |

## P2 — 冲 SOTA

| # | 方案条目 | 代码文件 | 实现要点 |
|---|---|---|---|
| 9 | RAG over writeups，失败时自我反思式检索 + knowledge-hint 注入 | `ctf_agent_kit/rag/writeup_store.py` | 倒排索引 + TF-IDF 打分；`reflect_and_retrieve()` 从失败摘要抽取关键词检索，`render_hints()` 生成注入块 |
| 10 | 多轨迹并行采样 pass@k | `ctf_agent_kit/core/parallel.py` | `ParallelSampler.sample()` 线程池并行 k 条独立轨迹（独立笔记/预算/验证器），支持早期终止 |
| 11 | 独立验证器降假阳性 | `ctf_agent_kit/agents/validator.py` | 不复用产出方上下文，按复现步骤独立重放；flag 需全部步骤稳定复现才判 high confidence |
| 12 | 接入 NYU CTF Bench / Cybench，报告 pass@1/pass@5 与成本，按类别预算上限 | `ctf_agent_kit/bench/runner.py` | JSONL 任务清单加载；`BenchReport` 含 pass@1/pass@k、按类别分解、成本/用时汇总；单题崩溃不拖垮整轮 |

## 攻防特化（硬性要求）

| 条目 | 代码文件 |
|---|---|
| 六类攻击 playbook（特征识别→工具→攻击链→变体） | `ctf_agent_kit/offense/playbooks/{crypto,reverse,pwn,web,forensics,misc}.md` |
| 蓝队日志/流量分析 | `ctf_agent_kit/defense/log_analyzer.py`（IOC 规则库、异常统计、攻击时间线） |
| 漏洞成因分析 / 修复建议 / 应急 checklist | `ctf_agent_kit/defense/playbooks/{vuln_root_cause,remediation,incident_checklist}.md` |

## 题型学习优化（硬性要求）

| 条目 | 代码文件 |
|---|---|
| 题型自动分类（规则法） | `ctf_agent_kit/learning/classifier.py`（关键词权重 + 附件强特征 + 可解释理由） |
| 知识点复盘 | `ctf_agent_kit/learning/review.py`（LLM 钩子 + 规则兜底，错题间隔重复调度） |
| 题库回放 | `ctf_agent_kit/learning/replay.py`（JSONL 归档、错题集、到期重练、few-shot 素材池） |

## 模型层

| 条目 | 代码文件 |
|---|---|
| 三模型配置 + 路由规则 + 降级链 + env key 占位 | `config/models.yaml` |
| 零依赖路由器（内置极简 YAML 解析器） | `ctf_agent_kit/models/router.py` |
