# ctf_agent_kit —— CTF 攻防特训智能体

一个面向 CTF 竞赛与授权靶场的攻防双特化智能体工具包：覆盖 crypto / reverse / pwn / web / forensics / misc 六大题型，内置自主攻击链路（信息收集 → 漏洞识别 → 漏洞利用 → flag 提取）与蓝队防御模块，并按「CTF 题型学习」做了专门优化（自动分类、知识点复盘、错题回放）。

- 全库**零第三方依赖**（纯标准库实现骨架，接口清晰、关键逻辑真实可用）
- 模型层配置驱动：更换模型只改 `config/models.yaml`
- 设计对标业界标杆：EnIGMA / D-CIPHER / CRAKEN / PentestGPT / HPTSA / Cybench（详见 `docs/OPTIMIZATION_MAP.md`）

## 架构图

```mermaid
flowchart TD
    subgraph 模型层
        R[models/router.py<br/>角色路由+降级链]
        CFG[config/models.yaml<br/>deepseek-r1 / qwen2.5-72b / deepseek-v4-flash]
    end

    subgraph 多角色智能体 agents/
        P[Planner<br/>全局计划+动态修订]
        AP[AutoPrompter<br/>指令精化+失败重派]
        E[Executor<br/>独立会话执行<br/>只回传摘要]
        V[Validator<br/>独立复核降假阳性]
    end

    subgraph 核心机制 core/
        FV[flag_verifier<br/>格式配置化+提交循环]
        B[budget<br/>轮次/成本上限+give_up]
        N[notes<br/>结构化笔记+LM摘要钩子]
        G[guardrails<br/>幻觉防护]
        PTT[ptt<br/>任务树叶子节点校验]
        PAR[parallel<br/>pass@k并行采样]
    end

    subgraph 工具与沙箱
        SH[tools/interactive_shell<br/>pwntools风格持久连接]
        GDB[tools/gdb_session<br/>gdb MI2交互会话]
        SB[sandbox/<br/>每题独立docker-compose]
    end

    subgraph 攻防特化
        OFF[offense/playbooks/<br/>六类攻击playbook]
        DEF[defense/<br/>日志分析+成因分析+修复+应急]
    end

    subgraph 学习优化 learning/
        CL[classifier 题型自动分类]
        RV[review 知识点复盘]
        RP[replay 题库回放]
    end

    RAG[rag/writeup_store<br/>自我反思式检索+hint注入]
    BN[bench/runner<br/>NYU CTF Bench/Cybench]

    CFG --> R
    R --> P & E & AP & V
    P --> AP --> E
    E --> SH & GDB
    E --> FV
    E -.-> V
    P <--> PTT
    E --> N
    G --> E
    B --> E
    PAR --> E
    OFF --> AP
    RAG --> AP
    SB --> E
    BN --> PAR
    E --> RV --> RP
    CL --> AP
    RP --> AP
```

## 六大题型支持矩阵

| 类别 | few-shot demo | 攻击 playbook | 专属工具 | 评测预算上限 |
|---|---|---|---|---|
| crypto | ✅ `prompts/demos/crypto.md` | ✅ RSA/分组/古典/PRNG | 自研求解脚本 + sage/gmpy2 接口位 | 30 轮 / $2 |
| reverse | ✅ `prompts/demos/reverse.md` | ✅ 脱壳/反编译/符号执行 | gdb 会话、angr/z3 接口位 | 40 轮 / $3 |
| pwn | ✅ `prompts/demos/pwn.md` | ✅ 栈/堆/fmt/orw | pwntools 风格持久 shell + gdb | 60 轮 / $5 |
| web | ✅ `prompts/demos/web.md` | ✅ 注入/文件/逻辑/反序列化 | curl/扫描器封装 | 40 轮 / $3 |
| forensics | ✅ `prompts/demos/forensics.md` | ✅ pcap/内存/磁盘/日志 | tshark/volatility 封装 | 30 轮 / $2 |
| misc | ✅ `prompts/demos/misc.md` | ✅ 编码套娃/隐写/OSINT | binwalk/zsteg/steghide 封装 | 30 轮 / $2 |

## 攻击 / 防御双模块

**红队（offense）**：`offense/playbooks/` 六类攻击 playbook（题型特征识别 → 常用工具 → 标准攻击链 → 常见变体），由 AutoPrompter 按题注入 Executor；配合持久 shell / gdb 会话形成完整攻击链。

**蓝队（defense）**：
- `defense/log_analyzer.py`：日志/流量 IOC 扫描（内置 8 类规则）、Top IP、状态码分布、速率突增检测、攻击时间线还原
- `defense/playbooks/vuln_root_cause.md`：漏洞成因分析框架（五类归因 + 报告模板）
- `defense/playbooks/remediation.md`：分漏洞类型的修复建议模板（P0–P3 优先级）
- `defense/playbooks/incident_checklist.md`：应急处置四阶段 checklist（含 AWD 赛制特化）

## 快速开始

```bash
# 1. 配置 API key（任选其一即可跑降级链）
export DEEPSEEK_API_KEY=sk-xxx
export QWEN_API_KEY=sk-xxx

# 2. 验证安装（零依赖，Python 3.9+）
python -m py_compile $(find ctf_agent_kit -name "*.py")

# 3. 试一下核心组件
python - <<'EOF'
from ctf_agent_kit.core import FlagVerifier, Budget, Notebook
from ctf_agent_kit.learning import classify

print(classify("截获RSA加密通信，附件pubkey.pem"))  # → crypto

fv = FlagVerifier()
ok, results = fv.scan_and_submit("输出: flag{demo_123}")
print(ok, fv.summary())

b = Budget.for_category("pwn")
print(b.report())
EOF

# 4. 跑示例题（凯撒密码）
cd ctf_agent_kit/sandbox/challenges/example_caesar && sh start.sh

# 5. 基准评测骨架
python -m ctf_agent_kit.bench.runner  # 接入自己的 solve_driver 即可跑 NYU CTF Bench / Cybench
```

## 目录结构

```
ctf_agent_kit/
├── config/models.yaml          # 模型配置（路由/降级链/env key 占位）
├── ctf_agent_kit/              # Python 包（零第三方依赖）
│   ├── models/router.py        # 模型路由器（内置极简 YAML 解析器）
│   ├── core/                   # flag验证/预算/笔记/幻觉防护/PTT/并行采样
│   ├── prompts/demos/          # 六大类 few-shot 解题轨迹（Markdown）
│   ├── agents/                 # Planner/Executor/AutoPrompter/Validator
│   ├── tools/                  # 持久 shell / gdb 会话
│   ├── sandbox/                # docker-compose 模板 + metadata schema + 示例题
│   ├── rag/writeup_store.py    # writeup 检索 + knowledge-hint 注入
│   ├── bench/runner.py         # NYU CTF Bench / Cybench 评测
│   ├── offense/playbooks/      # 红队六类攻击 playbook
│   ├── defense/                # 蓝队日志分析 + 成因/修复/应急 playbook
│   └── learning/               # 题型分类 / 复盘 / 题库回放
├── docs/OPTIMIZATION_MAP.md    # 优化方案 P0–P2 逐条映射
├── docs/CTF_TAXONOMY.md        # 六大题型知识库
└── README.md
```

## 与优化方案的对应关系

| 方案条目 | 落地位置 |
|---|---|
| P0-1 flag 验证器 + give_up | `core/flag_verifier.py` + `core/budget.py` |
| P0-2 类别化 few-shot demos | `prompts/demos/`（六类各一条完整轨迹） |
| P0-3 结构化笔记 + LM 摘要 | `core/notes.py` |
| P0-4 幻觉防护 | `core/guardrails.py` |
| P1-5 Planner–Executor 分离 | `agents/planner.py` / `executor.py` / `auto_prompter.py` |
| P1-6 交互式工具 | `tools/interactive_shell.py` / `tools/gdb_session.py` |
| P1-7 PTT 叶子节点校验 | `core/ptt.py` |
| P1-8 Docker 沙箱 + 题目封装 | `sandbox/` |
| P2-9 RAG over writeups | `rag/writeup_store.py` |
| P2-10 多轨迹并行采样 | `core/parallel.py` |
| P2-11 独立验证器 | `agents/validator.py` |
| P2-12 基准评测 | `bench/runner.py` |

逐条详细映射见 [docs/OPTIMIZATION_MAP.md](docs/OPTIMIZATION_MAP.md)。

## Benchmark 目标

- 基准：NYU CTF Bench（200 题）、Cybench（40 题含子任务）
- 指标：pass@1 / pass@5、按类别分解、成本与用时
- 目标：对标并超过当前 SOTA **22%**（CRAKEN，NYU CTF Bench）；裸 GPT-4 基线仅 3–4%
- 策略：P0 全量 + P1 架构 + P2 检索增强/多轨迹/独立验证器组合，按类别预算上限控制长尾成本

## 安全与合规声明

本项目**仅用于授权环境**：CTF 竞赛、自有靶场、安全培训与教学、获得书面授权的渗透测试。

- 禁止对未授权目标使用本项目中的任何攻击能力
- 沙箱默认启用只读文件系统、降权、资源限额等隔离基线
- 所有攻防 playbook 与工具调用日志留痕，便于审计
- 使用者须遵守所在司法辖区的法律法规，违法使用后果自负
