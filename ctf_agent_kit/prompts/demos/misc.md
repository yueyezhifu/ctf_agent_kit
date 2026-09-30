# Misc 解题演示（few-shot 轨迹）

> 题型：编码套娃 + 隐写混合题。

## 题目

```
category: misc
description: 一张看似普通的图片，但出题人说「眼见未必为实」。
attachments: innocent.png
```

## 解题轨迹

### Round 1 — 信息收集

**工具调用** `shell`:
```bash
file innocent.png; exiftool innocent.png | head -20; binwalk innocent.png
```
**输出摘录**:
```
innocent.png: PNG image data, 800 x 600
Comment: aGVsbG8gd29ybGRfdGhpc19pc19ub3RfdGhlX2ZsYWc=
JPEG image data ... at offset 0x12345
```

**笔记更新**:
- 已知事实: PNG 内含 Base64 注释（解码后明确说不是 flag，是干扰）；
  binwalk 发现内嵌 JPEG〔证据: shell#1〕
- 下一步候选: 提取内嵌 JPEG，继续做隐写分析

### Round 2 — 漏洞识别（提取内嵌文件）

**工具调用** `shell`:
```bash
binwalk -e innocent.png && ls _innocent.png.extracted/
```
**输出**: `12345  12345.jpg`

**工具调用** `shell`:
```bash
steghide info _innocent.png.extracted/12345.jpg 2>&1 | head -5
zsteg -a innocent.png 2>/dev/null | grep -i flag | head -3
```
**输出摘录**:
```
steghide: 需要密码
zsteg: b1,lsb,xy .. text: "flag{lsb_st3g0_"
```

**笔记更新**:
- 已知事实: 原 PNG 的 LSB 里藏了 flag 前半段；JPEG 的 steghide 需要密码〔证据: shell#3〕

### Round 3 — 利用（密码拼接）

**思考**: Base64 注释解码得 `hello_world_this_is_not_the_flag`——不是 flag 但可能是 steghide 密码。试试。

**工具调用** `shell`:
```bash
steghide extract -sf _innocent.png.extracted/12345.jpg -p "hello_world_this_is_not_the_flag"
cat steg.txt 2>/dev/null
```
**输出**:
```
wrote extracted data to "steg.txt"
w4s_h1dd3n_tw1c3}
```

**笔记更新**:
- 已知事实: 后半段 `w4s_h1dd3n_tw1c3}`，与 LSB 前半段拼接得完整 flag〔证据: shell#4〕

### Round 4 — 验证与提交

**工具调用** `submit_flag`: `flag{lsb_st3g0_w4s_h1dd3n_tw1c3}` → `✓ accepted`

## 复盘要点

1. Misc 套娃题：每层的「明显答案」常是下一层的钥匙而非终点。
2. 标准流程：file → exiftool → binwalk → 针对性隐写工具（zsteg/steghide）。
3. 分段 flag 拼接后整体过验证器，不要分段提交。
