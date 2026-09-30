# Pwn 攻击 Playbook

## 题型特征识别

- 附件：ELF 二进制 + libc/ld + 源码（可选）+ 远端 nc 地址
- 关键词：`nc host port`, `bof`, `heap`, `fmt`, `uaf`, `rop`
- checksec 结果直接决定攻击路线

## 常用工具

- 环境：pwntools、checksec、patchelf（换 libc 调试）
- 分析：gdb(+pwndbg)、ROPgadget、ropper、one_gadget
- 堆：pwndbg heap 命令族、how2heap 案例库
- libc 识别：libc.rip / libc.blukat.me（泄露地址查版本）

## 标准攻击链

1. **保护评估**：checksec 四项 → 定路线
   - 无 Canary + 无 PIE → 栈溢出 ret2plt/ret2libc
   - NX 关 → shellcode；PIE 开 → 先泄地址
2. **漏洞定位**：审源码/反编译找危险函数（gets/strcpy/scanf %s/UAF/double free）
3. **偏移与控制**：cyclic 定位 EIP/RIP 偏移；gdb 会话验证崩溃点可控
4. **构造利用**：
   - ret2libc：两阶段（泄 puts@got 算基址 → system("/bin/sh")）
   - 栈上无足够空间 → stack pivot / ret2csu
   - 格式化字符串：%p 泄露 + %n 改写 GOT
   - 堆：tcache poisoning / unsorted bin leak / house of 系列
5. **拿 shell 或 cat flag**：orw（open-read-write）替代 execve 应对 seccomp
6. **持久连接**：全程 pwntools 单连接，两阶段利用不断链

## 常见变体

- 64 位 ret2plt 需 pop rdi gadget 传参
- seccomp 沙箱 → 只允许 open/read/write → orw 读 flag
- kernel pwn / v8 pwn：单独 playbook，先识别再切换
- canary 泄露：格式化字符串或逐字节爆破（fork 型服务）
