# Reverse 解题演示（few-shot 轨迹）

> 题型：ELF 可执行文件逆向，关键校验函数定位 + 约束求解。

## 题目

```
category: reverse
description: 这个 crackme 要输入正确的 key 才能拿到 flag。
attachments: crackme (ELF x86-64, stripped)
```

## 解题轨迹

### Round 1 — 信息收集

**思考**: 先确认文件类型、保护机制、是否加壳。

**工具调用** `shell`:
```bash
file crackme; checksec --file=crackme; strings -n 6 crackme | head -40
```
**输出摘录**:
```
crackme: ELF 64-bit LSB pie executable, x86-64, stripped
Canary: ✓  NX: ✓  PIE: ✓  RelRO: Full
strings: "Usage: ./crackme <key>", "Correct!", "Wrong key", "upx"
```

**笔记更新**:
- 已知事实: ELF64 stripped PIE，strings 出现 "upx" 字样，疑似 UPX 加壳〔证据: shell#1〕
- 下一步候选: 脱壳后反编译，定位 key 校验逻辑

### Round 2 — 脱壳与静态分析

**工具调用** `shell`:
```bash
upx -d crackme -o crackme_unpacked && file crackme_unpacked
```
**输出**: `crackme_unpacked: ELF 64-bit LSB pie executable ... not stripped`

**工具调用** `shell`:
```bash
objdump -d crackme_unpacked | grep -A2 "<main>:" | head; nm crackme_unpacked | grep -i check
```
**输出摘录**:
```
0000000000001289 <main>:
00000000000011c0 <check_key>:
```

**笔记更新**:
- 已知事实: 脱壳成功，存在 `check_key` 函数〔证据: shell#3〕

### Round 3 — 漏洞识别（校验逻辑还原）

**工具调用** `gdb_session`:
```
gdb ./crackme_unpacked
> disassemble check_key
```
**输出摘录**:
```
check_key: 循环 32 次: input[i] ^ key_table[i] == target[i]
key_table 在 .rodata 0x2030
```

**思考**: 校验是逐字节 XOR 比对，直接静态提取两张表异或即得 key，无需动态爆破。

### Round 4 — 利用

**工具调用** `shell`:
```bash
python3 solve.py  # 读 .rodata 的 key_table/target，逐字节 XOR
```
**输出**:
```
[+] key = K3y_0f_R3v3rs1ng_2024!
[*] flag format -> flag{K3y_0f_R3v3rs1ng_2024!}
```

### Round 5 — 验证与提交

**工具调用** `shell`:
```bash
./crackme_unpacked 'K3y_0f_R3v3rs1ng_2024!'
```
**输出**: `Correct! flag{K3y_0f_R3v3rs1ng_2024!}`

**工具调用** `submit_flag`: `flag{K3y_0f_R3v3rs1ng_2024!}` → `✓ accepted`

## 复盘要点

1. stripped 二进制先 strings 找壳特征；UPX 直接 `upx -d`。
2. 逐字节独立校验类 crackme 静态提取即可；复杂约束（多字节耦合）再上 z3/angr。
3. 本地程序自验 Correct 后再提交，省一次远端试错。
