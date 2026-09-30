# CTF 六大题型知识库（CTF Taxonomy）

> 供题型分类器校准、AutoPrompter 提示词组装、学习路径规划使用。

## 1. Crypto（密码学）

### 子类型
- 古典密码（凯撒/维吉尼亚/栅栏/摩斯）
- 对称加密误用（ECB  oracle、CBC 翻转、填充提示 Padding Oracle）
- RSA 系列（低指数、共模、广播、dp/dq 泄露、Coppersmith 部分泄露）
- 流密码/PRNG（MT19937 状态恢复、LFSR、密钥复用双轨 XOR）
- 椭圆曲线（弱曲线、无效点、ECDSA 随机数复用）
- 格密码（LLL、背包、HNP）
- 哈希（长度扩展、碰撞构造）

### 识别特征
附件含 `.pem` / `pubkey` / 大整数参数 n,e,c；描述含「加密/密文/密钥/oracle」；给出加密脚本源码。

### 常用工具
Python(pycryptodome/gmpy2)、SageMath、RsaCtfTool、factorDB、CyberChef、untwister

### 经典考点
RSA 参数弱点枚举顺序；分组模式可塑性；PRNG 可预测性；数学推导转代码

### 学习路径
古典密码 → 分组模式 → RSA 数学基础 → Coppersmith/格 → 侧信道概念

## 2. Reverse（逆向工程）

### 子类型
- crackme（key/serial 校验）
- 壳与反调试（UPX/花指令/ptrace 检测/SMC）
- 虚拟机保护（自定义 opcode）
- 移动/托管平台（APK/dex、pyc、.NET、wasm）
- 算法还原（加密 flag 内嵌）

### 识别特征
附件为 ELF/PE/APK/pyc/class；程序要输入正确 key；无远端服务。

### 常用工具
IDA Pro / Ghidra、gdb(pwndbg)、x64dbg、frida、upx、pycdc、jadx、z3、angr

### 经典考点
由字符串 xref 定位校验函数；静态表提取 vs 约束求解的取舍；运行时 dump

### 学习路径
x86 汇编与 ABI → IDA/Ghidra 静态分析 → gdb 动态调试 → 脱壳 → 符号执行

## 3. Pwn（二进制利用）

### 子类型
- 栈溢出（ret2plt / ret2libc / ret2csu / SROP）
- 格式化字符串（泄露 + 任意写）
- 堆利用（tcache poisoning、UAF、double free、unsorted bin leak、house of 系列）
- 沙箱逃逸（seccomp 下 orw）
- 内核/浏览器（进阶）

### 识别特征
附件含 ELF + libc.so.6 + ld-linux；远端 `nc host port`；描述含「溢出/堆/fmt」。

### 常用工具
pwntools、checksec、gdb(pwndbg/gef)、ROPgadget、one_gadget、patchelf、libc 数据库

### 经典考点
checksec 四象限定路线；泄露-计算-利用三段式；堆风水布局

### 学习路径
栈基础 → ROP → 格式化字符串 → glibc 堆（how2heap 全套）→ 内核入门

## 4. Web

### 子类型
- 注入（SQLi 报错/联合/盲注、命令注入、SSTI、LDAP/XPath）
- 文件类（LFI/RFI、伪协议、任意上传、路径穿越）
- 逻辑类（越权 IDOR、条件竞争、JWT 伪造、业务逻辑绕过）
- 反序列化（PHP/Java/Python/.NET）
- SSRF（内网探测、gopher 打内网服务）
- 前端（JS 审计、wasm、CORS/CSRF）

### 识别特征
给出 URL 或源码包；描述含「网站/登录/上传/admin」；附件为 PHP/Java/Python 源码或 docker 部署文件。

### 常用工具
Burp Suite、curl、dirsearch、sqlmap（确认注入点后）、ysoserial、phpggc、jwt_tool

### 经典考点
攻击面测绘先行；报错回显即路标；部分 flag 拼接套路；源码审计污点追踪

### 学习路径
HTTP 协议与 Burp → OWASP Top10 逐类打靶 → 反序列化链 → 组合拳与内网

## 5. Forensics（取证）

### 子类型
- 流量分析（pcap：HTTP 对象、DNS/ICMP 隧道、USB HID、无线）
- 内存取证（volatility：进程/注入/凭据/dump）
- 磁盘取证（镜像挂载、已删文件恢复、时间线）
- 日志分析（入侵时间线、IOC 匹配）
- 文件修复（头修复、CRC 爆破、分片重组）

### 识别特征
附件为 `.pcap/.pcapng/.mem/.img/.vmem` 或大量日志；描述含「捕获/取证/入侵/窃取」。

### 常用工具
Wireshark/tshark、NetworkMiner、volatility3、binwalk、foremost、photorec、010 Editor

### 经典考点
协议层级统计找异常；分片重组去重排序；干扰项识别；字节级还原为最终裁决

### 学习路径
Wireshark 熟练度 → pcap 专项 → volatility 内存三件套 → 磁盘镜像综合案例

## 6. Misc（杂项）

### 子类型
- 编码套娃（Base 家族/hex/rot/摩斯/二维码 多层嵌套）
- 隐写（图片 LSB/元数据/追加数据、音频频谱/SSTV、文档隐写）
- 压缩包破解（弱密码、明文攻击、CRC32 爆破）
- OSINT（地理定位、社交检索、域名历史）
- 游戏/脚本/量子/AI/区块链（新题型）

### 识别特征
难以归入前五类；附件为图片/音频/奇怪格式；描述含「隐写/眼见未必为实/找线索」。

### 常用工具
CyberChef(Magic)、zsteg、steghide、stegsolve、Audacity、john/hashcat、binwalk

### 经典考点
套娃心态：每层答案是下层钥匙；标准侦察三连（file/exiftool/binwalk）；分段 flag 拼接

### 学习路径
编码识别直觉 → 图片隐写全家桶 → 音频/文档介质 → OSINT 方法论 → 新题型靠 writeup 检索（rag/writeup_store）
