# Forensics 解题演示（few-shot 轨迹）

> 题型：流量包分析（pcap）+ 数据还原。

## 题目

```
category: forensics
description: 我们捕获了攻击者的网络流量，找出他偷走了什么。
attachments: capture.pcap
```

## 解题轨迹

### Round 1 — 信息收集

**工具调用** `shell`:
```bash
file capture.pcap; capinfos capture.pcap 2>/dev/null | head -10
tshark -r capture.pcap -q -z io,phs 2>/dev/null | head -30
```
**输出摘录**:
```
capture.pcap: pcap capture file, tcpdump
Protocol Hierarchy: tcp 82%, http 45%, dns 20%, icmp 17%
```

**笔记更新**:
- 已知事实: 流量以 HTTP/DNS 为主，另有 17% ICMP 异常占比〔证据: shell#1〕
- 下一步候选: HTTP 对象导出 + 检查 ICMP payload（ICMP 隧道外传）

### Round 2 — 漏洞识别（发现外传通道）

**工具调用** `shell`:
```bash
tshark -r capture.pcap -Y "http.request.method==POST" -T fields -e frame.number -e ip.dst -e http.request.uri | head
tshark -r capture.pcap -Y "icmp" -T fields -e data | head -20
```
**输出摘录**:
```
12  10.0.0.99  /upload.php
ICMP data: 666c61677b7000...   # 每次 8 字节，明显是分片传输
```

**笔记更新**:
- 已知事实: ICMP payload 携带十六进制数据，首片解码以 `flag{` 开头〔证据: shell#2〕

### Round 3 — 利用（重组数据）

**工具调用** `shell`:
```bash
tshark -r capture.pcap -Y "icmp && ip.src==10.0.0.5" -T fields -e data | tr -d '\n' > exfil.hex
python3 -c "
data = bytes.fromhex(open('exfil.hex').read())
print(data.decode(errors='replace'))
"
```
**输出**:
```
flag{1cmp_tunn31_3xf1ltr4t10n}
== exfil complete ==
```

### Round 4 — 验证与提交

**思考**: ICMP 重组得到完整 flag，与 HTTP POST 里上传的压缩包无关（干扰项）。直接提交。

**工具调用** `submit_flag`: `flag{1cmp_tunn31_3xf1ltr4t10n}` → `✓ accepted`

## 复盘要点

1. pcap 第一眼看协议层级统计，异常协议占比就是出题人留的路标。
2. 数据外传常分片：按源 IP 过滤、按序拼接、注意去重（ICMP 重传）。
3. HTTP 导出对象可能是干扰；结论以字节级还原结果为准。
