# Reverse 攻击 Playbook

## 题型特征识别

- 附件：ELF/PE/APK/pyc/class/dex → 对应平台逆向链
- 程序要输入 key/serial/password → crackme 类
- 行为异常但无输入接口 → 花指令/反调试/虚拟机保护类
- 关键词：`crackme`, `keygen`, `packed`, `vm`, `obfuscated`

## 常用工具

- 静态：IDA Pro / Ghidra / Binary Ninja、objdump、strings、radare2
- 动态：gdb(+pwndbg/gef)、x64dbg、frida
- 脱壳：upx -d、uncompyle6/pycdc（pyc）、jadx（APK）
- 求解：z3、angr（符号执行）

## 标准攻击链

1. **侦察**：`file` + `checksec` + `strings`，确认架构/壳/保护
2. **脱壳去混淆**：UPX 直接脱；花指令用 IDA 插件或手工 patch
3. **定位校验逻辑**：由成功/失败字符串 xref 反查主校验函数
4. **还原算法**：
   - 逐字节独立校验 → 静态提取两张表直接算
   - 多字节耦合约束 → z3 建模求解
   - 控制流复杂 → angr 符号执行到 "Correct" 分支
5. **本地自验**：程序输出 Correct 后再提交 flag

## 常见变体

- VM 保护：先还原 opcode 表，再翻译字节码为伪代码
- 反调试：ptrace 检测 patch 掉；SMC 自修改先 dump 运行时内存
- 加密 flag 内嵌：算法可逆则直接逆算，不可逆则动态 dump 解密后内存
- 多层套娃：pyc → py 源码 → 内嵌 ELF，逐层剥离
