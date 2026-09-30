# Crypto 攻击 Playbook

## 题型特征识别

- 附件含 `.pem` / `pubkey` / `n, e, c` 参数 → RSA 类
- 给出加密脚本源码 + 输出 → 代码审计找误用（ECB/重放/弱随机）
- 大量十六进制/Base64 字符串 → 编码/古典密码
- 关键词：`encrypted`, `cipher`, `oracle`, `shared secret`, `prng`

## 常用工具

- 通用：Python（pycryptodome/gmpy2）、sage、CyberChef
- RSA：RsaCtfTool、factorDB（在线分解）、yafu
- 古典：quipqiup、dcode.fr
- 随机数：untwister（MT19937 状态恢复）

## 标准攻击链

1. **参数提取**：从附件/源码读出所有已知量（n, e, c, p 的线索）
2. **弱点匹配**：
   - n 可分解（factorDB 命中/费马近邻）→ 直接求 d
   - e 极小（3）→ 低指数攻击 / 广播攻击（Håstad）/ Franklin-Reiter
   - 同 n 不同 e 同明文 → 共模攻击（扩展欧几里得）
   - 同密钥多密文流密码 → 双轨 XOR（crib dragging）
   - ECB 分组 → 逐字节 Oracle 解密
   - MT19937 弱种子 → 状态恢复/预测
3. **脚本化利用**：写 solve.py，输出候选明文
4. **flag 提取验证**：候选过 FlagVerifier，格式匹配 ≠ 正确，必须远端/精确验证

## 常见变体

- RSA 变种：多素数 RSA、Common Prime RSA、dp/dq 泄露、LSB 泄露（Coppersmith）
- 格密码：LLL 规约解背包/HNP
- 侧信道模拟题：时序/功耗数据拟合
- 自定义算法：先还原算法结构，再找可逆性/差分弱点
