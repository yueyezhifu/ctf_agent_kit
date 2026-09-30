# 示例题：凯撒的秘密（crypto / easy）

## 启动

```bash
cd ctf_agent_kit/sandbox/challenges/example_caesar
sh start.sh        # 本地模式
# 或由 SandboxManager 渲染 compose 后 docker compose up -d
```

## 解题提示

凯撒移位 ≤25，直接枚举 25 种移位，用 flag 前缀 `flag{` 命中即可：

```python
ct = open("ciphertext.txt").read().lower()
for s in range(26):
    pt = "".join(chr((ord(c)-97-s)%26+97) if c.isalpha() else c for c in ct)
    if "flag{" in pt:
        print(s, pt)
```
